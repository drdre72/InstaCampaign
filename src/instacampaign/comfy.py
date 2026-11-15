"""ComfyUI HTTP client — generation backend.

ComfyUI runs as a local server (default 127.0.0.1:8188, started with
`--listen 127.0.0.1 --port 8188`). The pipeline submits an API-format
workflow JSON with placeholders filled, polls /history, then downloads
output images via /view.

Workflow templates are plain API-format JSON with three placeholder tokens:
  {{PROMPT}}  positive prompt text (injected json-escaped)
  {{NEGATIVE}} negative prompt text
  {{SEED}}    integer seed
  {{PREFIX}}  ComfyUI filename_prefix for outputs
See comfy/workflows/README.md.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .util import ROOT, settings


class ComfyError(Exception):
    pass


class ComfyClient:
    def __init__(self, base: str | None = None, timeout_s: int | None = None):
        cfg = settings().get("comfy", {})
        self.base = (base or cfg.get("base_url")
                     or "http://127.0.0.1:8188").rstrip("/")
        self.timeout_s = int(timeout_s or cfg.get("timeout_s", 600))

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except Exception as e:
            raise ComfyError(f"comfy {method} {path}: {e}")

    def ping(self) -> dict:
        return self._req("GET", "/system_stats")

    def submit(self, workflow: dict) -> str:
        resp = self._req("POST", "/prompt", {"prompt": workflow})
        pid = resp.get("prompt_id")
        if not pid:
            raise ComfyError(f"no prompt_id in response: {resp}")
        return pid

    def history(self, prompt_id: str) -> dict:
        return self._req("GET", f"/history/{prompt_id}")

    def wait(self, prompt_id: str, poll_s: float = 2.0) -> dict:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            hist = self.history(prompt_id)
            if prompt_id in hist:
                return hist[prompt_id]
            time.sleep(poll_s)
        raise ComfyError(f"timed out waiting for {prompt_id}")

    def download(self, filename: str, subfolder: str = "",
                 type_: str = "output") -> bytes:
        q = urllib.parse.urlencode(
            {"filename": filename, "subfolder": subfolder, "type": type_})
        req = urllib.request.Request(f"{self.base}/view?{q}")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            raise ComfyError(f"comfy download {filename}: {e}")

    def collect(self, prompt_id: str) -> list[tuple[str, bytes]]:
        entry = self.wait(prompt_id)
        outputs = entry.get("outputs", {})
        files: list[tuple[str, bytes]] = []
        for node in outputs.values():
            for img in node.get("images", []):
                files.append((img["filename"],
                              self.download(img["filename"],
                                            img.get("subfolder", ""),
                                            img.get("type", "output"))))
        if not files:
            raise ComfyError(f"prompt {prompt_id} produced no images")
        return files


def load_workflow(path: str | Path | None = None) -> str:
    p = Path(path or ROOT / settings().get("comfy", {})
             .get("workflow", "comfy/workflows/persona_flux.json"))
    if not p.exists():
        raise ComfyError(f"workflow template not found: {p}")
    return p.read_text()


def fill_workflow(raw: str, *, prompt: str, seed: int,
                  prefix: str, negative: str = "") -> dict:
    def esc(s: str) -> str:
        return json.dumps(str(s))[1:-1]      # escaped, quotes stripped
    out = (raw.replace("{{PROMPT}}", esc(prompt))
              .replace("{{NEGATIVE}}", esc(negative))
              .replace("{{SEED}}", str(int(seed)))
              .replace("{{PREFIX}}", esc(prefix)))
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise ComfyError(f"filled workflow is not valid json: {e}")
