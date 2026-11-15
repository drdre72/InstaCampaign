"""Seeded content planning.

A plan is a deterministic weekly schedule of posts for one persona. The same
(persona spec hash, week, seed) must regenerate the identical plan — plans
are hashed and bound to renders downstream.

LLM-assisted captions/scenarios are an optional later refinement; the
baseline planner emits template captions carrying the disclosure tag, which
is required on every post regardless of generation method.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .persona import REQUIRED_BANNED, PersonaError
from .util import ROOT, atomic_write_text, sha256_json

FORMATS = ("image", "carousel", "reel")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# Roughly IG-portrait slots; actual clock times are a scheduling concern.
DAY_SLOTS = ("18:00", "12:00", "19:00", "17:00", "20:00", "11:00", "16:00")
DISCLOSURE_TAG = "#AIGenerated"


class PlanError(Exception):
    pass


def assemble_prompt(spec: dict, theme: str) -> str:
    style = spec["identity"]["style_prompt"].rstrip(", ")
    parts = [style, str(theme).strip(), "instagram photo, sfw"]
    if spec["content"].get("wardrobe"):
        pass  # wardrobe tokens arrive via themes; kept for spec stability
    return ", ".join(p for p in parts if p)


def build_plan(spec: dict, week: str, seed: int,
               posts: int | None = None) -> dict:
    n = posts or int(spec["posting"]["cadence_per_week"])
    if not 1 <= n <= 21:
        raise PlanError("posts must be 1..21")
    rng = random.Random(f"{spec['name']}:{week}:{seed}")
    themes = list(spec["content"]["themes"])
    days = sorted(rng.sample(range(7), k=min(n, 7)))
    while len(days) < n:                       # extra posts share later days
        days.append(days[-1] if days else rng.randrange(7))
    items = []
    for i in range(n):
        theme = themes[rng.randrange(len(themes))]
        item = {
            "index": i,
            "day": DAYS[days[i]],
            "slot_utc": DAY_SLOTS[days[i]],
            "theme": theme,
            "format": "image",                  # reels opt-in per item later
            "seed": rng.randrange(2**31),
            "prompt": assemble_prompt(spec, theme),
            "caption": f"{spec['display_name']} | {theme} {DISCLOSURE_TAG}",
        }
        items.append(item)
    return {
        "name": f"{spec['name']}-{week}",
        "persona": spec["name"],
        "persona_sha": sha256_json(spec),
        "week": week,
        "seed": seed,
        "rating": spec["content"]["rating"],
        "items": items,
    }


def validate_plan(plan: dict, spec: dict) -> None:
    if plan.get("persona") != spec["name"]:
        raise PlanError("plan bound to different persona")
    if plan.get("persona_sha") != sha256_json(spec):
        raise PlanError("persona spec changed since plan was built")
    if plan.get("rating") != spec["content"]["rating"]:
        raise PlanError("plan rating drifted from spec")
    banned = REQUIRED_BANNED | {str(b).lower()
                                for b in spec["content"].get("banned", [])}
    for item in plan.get("items", []):
        if item.get("format") not in FORMATS:
            raise PlanError(f"bad format: {item.get('format')}")
        blob = json.dumps(item).lower()
        if any(b in blob for b in banned):
            raise PlanError(f"banned term in item {item.get('index')}")
    if not plan.get("items"):
        raise PlanError("plan has no items")


def plan_sha256(plan: dict) -> str:
    return sha256_json(plan)


def save_plan(plan: dict) -> Path:
    p = ROOT / "plans" / f"{plan['name']}.json"
    atomic_write_text(p, json.dumps(plan, indent=2, sort_keys=True))
    return p


def load_plan(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise PlanError(f"plan not found: {p}")
    try:
        plan = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise PlanError(f"invalid plan json: {e}")
    for key in ("name", "persona", "persona_sha", "week", "seed",
                "rating", "items"):
        if key not in plan:
            raise PlanError(f"plan missing key: {key}")
    return plan
