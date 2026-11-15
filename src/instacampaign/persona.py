"""Persona spec: a synthetic, disclosed-AI identity with a hard SFW ceiling.

Validation is fail-closed — spec errors raise PersonaError before anything
is stored or generated. The spec hash is the identity of the persona version;
any spec edit produces a new hash, which invalidates nothing retroactively
but changes what future plans bind to.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .util import sha256_json

ALLOWED_RATINGS = {"sfw", "pg13"}
# Minimum banned-content list — specs may add more, never remove these.
REQUIRED_BANNED = {"nudity", "explicit", "gore"}
DISCLOSURE_HINTS = ("ai", "generated", "virtual", "synthetic", "digital")
MAX_CADENCE_PER_WEEK = 21          # IG API cap is 100/24h; stay far under


class PersonaError(Exception):
    pass


def load_spec(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise PersonaError(f"spec not found: {p}")
    try:
        spec = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise PersonaError(f"invalid yaml: {e}")
    if not isinstance(spec, dict):
        raise PersonaError("spec must be a mapping")
    return spec


def _disclosure_ok(text: str) -> bool:
    t = text.lower()
    return any(h in t for h in DISCLOSURE_HINTS)


def validate(spec: dict) -> dict:
    for key in ("name", "display_name", "bio", "disclosure", "identity",
                "content", "posting"):
        if key not in spec:
            raise PersonaError(f"missing required key: {key}")

    name = spec["name"]
    if not isinstance(name, str) or not name.replace("_", "").isalnum():
        raise PersonaError("name must be [a-z0-9_] snake-ish")
    if name != name.lower():
        raise PersonaError("name must be lowercase")

    if not _disclosure_ok(str(spec["disclosure"])):
        raise PersonaError(
            "disclosure must state the persona is AI/generated/virtual — "
            "undisclosed synthetic personas are not supported")

    ident = spec["identity"]
    if not ident.get("style_prompt"):
        raise PersonaError("identity.style_prompt is required")
    if not ident.get("reference_dir"):
        raise PersonaError("identity.reference_dir is required")

    content = spec["content"]
    rating = str(content.get("rating", "")).lower()
    if rating not in ALLOWED_RATINGS:
        raise PersonaError(
            f"content.rating must be one of {sorted(ALLOWED_RATINGS)} — "
            "explicit content is permanently out of scope")
    banned = {str(b).lower() for b in content.get("banned", [])}
    missing = REQUIRED_BANNED - banned
    if missing:
        raise PersonaError(f"content.banned must include {sorted(missing)}")
    themes = content.get("themes") or []
    if not themes:
        raise PersonaError("content.themes must be non-empty")
    style_blob = str(ident.get("style_prompt", "")).lower()
    for theme in themes:
        blob = str(theme).lower()
        if any(b in blob for b in REQUIRED_BANNED):
            raise PersonaError(f"banned term in theme: {theme}")
    if any(b in style_blob for b in REQUIRED_BANNED):
        raise PersonaError("banned term in identity.style_prompt")

    posting = spec["posting"]
    cadence = int(posting.get("cadence_per_week", 0))
    if not 1 <= cadence <= MAX_CADENCE_PER_WEEK:
        raise PersonaError(
            f"posting.cadence_per_week must be 1..{MAX_CADENCE_PER_WEEK}")

    spec["content"]["rating"] = rating
    return spec


def spec_sha(spec: dict) -> str:
    return sha256_json(spec)


def reference_dir(spec: dict) -> Path:
    from .util import ROOT
    return ROOT / spec["identity"]["reference_dir"]
