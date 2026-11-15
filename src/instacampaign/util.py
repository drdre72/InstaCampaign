from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def settings() -> dict:
    cfg = ROOT / "config" / "settings.yaml"
    return yaml.safe_load(cfg.read_text()) if cfg.exists() else {}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def atomic_write(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_text(p: Path, text: str) -> None:
    atomic_write(p, text.encode())


def out_dir() -> Path:
    d = ROOT / settings().get("paths", {}).get("output", "output")
    d.mkdir(parents=True, exist_ok=True)
    return d


def secrets_dir() -> Path:
    d = ROOT / settings().get("paths", {}).get("secrets", "secrets")
    d.mkdir(parents=True, exist_ok=True)
    return d


def run(argv: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{argv[0]} failed: {r.stderr[-600:]}")
    return r


def check(binary: str) -> str | None:
    return shutil.which(binary)
