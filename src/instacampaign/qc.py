"""QC gates. Every gate returns {gate, status, ...} where status is
pass | fail | needs_manual. A render's overall status:

    all pass            -> pass
    any fail            -> fail
    else (any manual)   -> needs_manual   (operator attestation required)

Gates fail closed: optional classifiers that aren't installed return
needs_manual, never an implicit pass. `qc.json` is written next to the
render artifact for every render.
"""
from __future__ import annotations

import json
from pathlib import Path

from .media import reel_errors
from .persona import reference_dir
from .util import atomic_write_text, settings

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov"}


def sfw_gate(path: Path) -> dict:
    """NSFW classifier gate. opennsfw2 optional; absent -> needs_manual."""
    try:
        import opennsfw2 as n2  # noqa: PLC0415 optional extra
    except ImportError:
        return {"gate": "sfw", "status": "needs_manual",
                "reason": "classifier not installed — operator attestation "
                          "required (uv sync --extra nsfw)"}
    try:
        score = float(n2.predict_image(str(path)))
    except Exception as e:
        return {"gate": "sfw", "status": "needs_manual",
                "reason": f"classifier error: {e}"}
    threshold = float(settings().get("qc", {}).get("nsfw_max", 0.2))
    return {"gate": "sfw",
            "status": "pass" if score < threshold else "fail",
            "score": round(score, 4), "threshold": threshold}


def face_gate(path: Path, spec: dict) -> dict:
    """Identity consistency: ArcFace embedding vs persona reference sheet."""
    ref = reference_dir(spec)
    try:
        import numpy as np  # noqa: PLC0415
        from insightface.app import FaceAnalysis  # noqa: PLC0415
    except ImportError:
        return {"gate": "face", "status": "needs_manual",
                "reason": "insightface not installed — operator attestation "
                          "required (uv sync --extra face)"}
    refs = sorted(p for p in ref.glob("*") if p.suffix.lower() in IMAGE_EXTS)
    if not refs:
        return {"gate": "face", "status": "needs_manual",
                "reason": f"no reference images in {ref}"}
    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))

    def emb(p: Path):
        import cv2  # noqa: PLC0415 bundled with insightface
        img = cv2.imread(str(p))
        faces = app.get(img) if img is not None else []
        return faces[0].normed_embedding if faces else None

    gen = emb(path)
    if gen is None:
        return {"gate": "face", "status": "fail",
                "reason": "no face detected in generated image"}
    ref_embs = [e for e in (emb(r) for r in refs) if e is not None]
    if not ref_embs:
        return {"gate": "face", "status": "needs_manual",
                "reason": "no faces found in reference sheet"}
    sim = float(max(np.dot(gen, e) for e in ref_embs))
    thresh = float(settings().get("qc", {}).get("face_similarity_min", 0.55))
    return {"gate": "face",
            "status": "pass" if sim >= thresh else "fail",
            "similarity": round(sim, 4), "threshold": thresh}


def media_gate(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        try:
            from PIL import Image  # noqa: PLC0415
            with Image.open(path) as im:
                im.verify()
            return {"gate": "media", "status": "pass", "kind": "image"}
        except Exception as e:
            return {"gate": "media", "status": "fail",
                    "reason": f"unreadable image: {e}"}
    if ext in VIDEO_EXTS:
        errs = reel_errors(path)
        return {"gate": "media",
                "status": "fail" if errs else "pass",
                "kind": "video", "errors": errs}
    return {"gate": "media", "status": "fail",
            "reason": f"unsupported extension {ext}"}


def run_qc(path: Path, spec: dict, out_path: Path | None = None) -> dict:
    gates = [media_gate(path), sfw_gate(path)]
    if path.suffix.lower() in IMAGE_EXTS:
        gates.append(face_gate(path, spec))
    statuses = {g["status"] for g in gates}
    overall = "fail" if "fail" in statuses else (
        "needs_manual" if "needs_manual" in statuses else "pass")
    qc = {"artifact": str(path), "persona": spec["name"], "status": overall,
          "gates": gates}
    dest = out_path or path.with_suffix(".qc.json")
    atomic_write_text(dest, json.dumps(qc, indent=2, sort_keys=True))
    return qc
