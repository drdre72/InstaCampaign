"""Instagram Graph API adapter — dormant by design.

Publishing through the official Content Publishing API requires:
  - a Professional (Business/Creator) IG account
  - secrets/meta.json with allowlisted keys: access_token, ig_user_id,
    app_id (migrated by the operator into gitignored secrets/, mode-600)
  - config publishing.uploads_enabled: true
  - a publicly reachable media_url (the API curls media from a URL —
    export package must be staged to a bucket/static host first)

For your OWN professional account, a Meta app in development mode with
Standard Access is sufficient — no app review. Until all gates pass, the
adapter refuses and `ig status` reports configuration only. The operator
uploads export packages manually in the meantime.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .persona import DISCLOSURE_HINTS
from .util import secrets_dir, settings

GRAPH = "https://graph.instagram.com"
ALLOWED_SECRET_KEYS = {"access_token", "ig_user_id", "app_id"}
API_POSTS_PER_24H = 100


class PublishError(Exception):
    pass


def secret_path() -> Path:
    return secrets_dir() / "meta.json"


def load_secrets() -> dict | None:
    p = secret_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    return {k: raw[k] for k in ALLOWED_SECRET_KEYS if k in raw}


def status() -> dict:
    secrets = load_secrets()
    cfg = settings().get("publishing", {})
    return {
        "client_configured": bool(secrets and secrets.get("access_token")
                                  and secrets.get("ig_user_id")),
        "uploads_enabled": bool(cfg.get("uploads_enabled", False)),
        "platform": cfg.get("platform", "instagram"),
        "note": "adapter dormant; exports are local-only until gated on",
    }


class InstagramPublisher:
    def __init__(self):
        self.cfg = settings().get("publishing", {})
        self.secrets = load_secrets()

    def _require(self, spec: dict | None = None) -> None:
        if not self.cfg.get("uploads_enabled", False):
            raise PublishError("uploads disabled — export packages only")
        if not self.secrets:
            raise PublishError("secrets/meta.json missing "
                               "(access_token, ig_user_id, app_id)")
        if spec is not None:
            d = str(spec.get("disclosure", "")).lower()
            if not any(h in d for h in DISCLOSURE_HINTS):
                raise PublishError("persona lacks AI disclosure — refusing")

    def _post(self, path: str, fields: dict) -> dict:
        data = urllib.parse.urlencode(
            {**fields, "access_token": self.secrets["access_token"]}).encode()
        req = urllib.request.Request(GRAPH + path, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")

    def _get(self, path: str, fields: dict) -> dict:
        q = urllib.parse.urlencode(
            {**fields, "access_token": self.secrets["access_token"]})
        req = urllib.request.Request(f"{GRAPH}{path}?{q}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")

    def publish(self, media_url: str, caption: str, *,
                media_type: str = "IMAGE", spec: dict | None = None) -> str:
        self._require(spec)
        ig = self.secrets["ig_user_id"]
        fields = {"caption": caption}
        if media_type == "REELS":
            fields.update({"media_type": "REELS", "video_url": media_url})
        elif media_type == "IMAGE":
            fields["image_url"] = media_url
        else:
            raise PublishError(f"unsupported media_type {media_type}")
        container = self._post(f"/{ig}/media", fields)
        cid = container.get("id")
        if not cid:
            raise PublishError(f"no container id: {container}")
        for _ in range(60):
            st = self._get(f"/{cid}", {"fields": "status_code"})
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise PublishError(f"container error: {st}")
            time.sleep(2)
        else:
            raise PublishError("container never finished processing")
        pub = self._post(f"/{ig}/media_publish", {"creation_id": cid})
        remote = pub.get("id")
        if not remote:
            raise PublishError(f"publish failed: {pub}")
        return remote
