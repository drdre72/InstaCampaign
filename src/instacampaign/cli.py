"""CLI: init / persona / plan / generate / qc / approve / export / ig /
status / doctor."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from pathlib import Path

from . import comfy as comfy_mod
from . import db as db_mod
from . import ig as ig_mod
from . import persona as persona_mod
from . import planner as planner_mod
from . import qc as qc_mod
from .persona import PersonaError
from .planner import PlanError, plan_sha256
from .util import (ROOT, atomic_write, check, out_dir, settings,
                   sha256_file)


def _spec_for(row) -> dict:
    return json.loads(row["spec_json"])


# ---- init ---------------------------------------------------------------

def cmd_init(_):
    db_mod.init_db()
    (ROOT / "plans").mkdir(exist_ok=True)
    (ROOT / "assets" / "personas").mkdir(parents=True, exist_ok=True)
    (ROOT / "secrets").mkdir(exist_ok=True)
    out_dir()
    print("initialized db, plans/, assets/personas/, secrets/, output/")


# ---- persona ------------------------------------------------------------

def cmd_persona_new(a):
    spec = persona_mod.validate(persona_mod.load_spec(a.spec))
    name = spec["name"]
    if db_mod.get_persona(name):
        raise SystemExit(f"persona exists: {name}")
    pid = db_mod.insert_persona(name, spec, persona_mod.spec_sha(spec))
    db_mod.event("persona_created", persona=name, sha=persona_mod.spec_sha(spec))
    ref = persona_mod.reference_dir(spec)
    ref.mkdir(parents=True, exist_ok=True)
    print(f"persona #{pid} {name} — drop the reference face sheet in {ref}")


def cmd_persona_list(_):
    for row in db_mod.list_personas():
        spec = _spec_for(row)
        print(f"{row['id']:>3}  {row['name']:20s} "
              f"{spec['content']['rating']:5s} "
              f"cadence={spec['posting']['cadence_per_week']}/wk "
              f"sha={row['sha256'][:12]}")


def cmd_persona_validate(a):
    try:
        spec = persona_mod.validate(persona_mod.load_spec(a.spec))
        print(json.dumps({"valid": True, "name": spec["name"],
                          "sha256": persona_mod.spec_sha(spec)}, indent=2))
    except PersonaError as e:
        raise SystemExit(f"INVALID: {e}")


# ---- plan ---------------------------------------------------------------

def cmd_plan_new(a):
    row = db_mod.get_persona(a.persona)
    if not row:
        raise SystemExit(f"unknown persona: {a.persona}")
    spec = _spec_for(row)
    plan = planner_mod.build_plan(spec, week=a.week, seed=a.seed,
                                  posts=a.posts)
    planner_mod.validate_plan(plan, spec)
    path = planner_mod.save_plan(plan)
    pid = db_mod.insert_plan(row["id"], plan["name"], plan,
                             plan_sha256(plan))
    db_mod.event("plan_created", plan_id=pid, persona=spec["name"],
                 items=len(plan["items"]))
    print(f"plan #{pid} {plan['name']} -> {path} "
          f"({len(plan['items'])} items, sha={plan_sha256(plan)[:12]})")


def cmd_plan_list(_):
    for row in db_mod.list_plans():
        plan = json.loads(row["plan_json"])
        print(f"{row['id']:>3}  {row['name']:24s} {row['status']:8s} "
              f"items={len(plan['items'])} sha={row['sha256'][:12]}")


def cmd_plan_validate(a):
    try:
        plan = planner_mod.load_plan(a.plan)
        row = db_mod.get_persona(plan["persona"])
        if not row:
            raise PlanError(f"unknown persona {plan['persona']}")
        planner_mod.validate_plan(plan, _spec_for(row))
        print(json.dumps({"valid": True, "name": plan["name"],
                          "sha256": plan_sha256(plan)}, indent=2))
    except (PlanError, PersonaError) as e:
        raise SystemExit(f"INVALID: {e}")


# ---- generate -----------------------------------------------------------

def cmd_generate(a):
    row = db_mod.get_plan(a.plan)
    if not row:
        raise SystemExit(f"unknown plan id: {a.plan}")
    plan = json.loads(row["plan_json"])
    prow = db_mod.get_persona(plan["persona"])
    spec = _spec_for(prow)
    planner_mod.validate_plan(plan, spec)
    client = comfy_mod.ComfyClient()
    client.ping()                                    # fail fast if down
    raw = comfy_mod.load_workflow(a.workflow)
    existing = {r["item_index"] for r in db_mod.list_renders()
                if r["plan_id"] == row["id"]}
    rdir = out_dir() / "renders" / f"{plan['name']}-{int(time.time())}"
    for item in plan["items"]:
        if item["index"] in existing:
            continue                                 # idempotent restart
        wf = comfy_mod.fill_workflow(
            raw, prompt=item["prompt"], seed=item["seed"],
            negative=spec["identity"].get("negative_prompt", ""),
            prefix=f"{plan['name']}-{item['index']:02d}")
        pid = client.submit(wf)
        db_mod.event("comfy_submitted", plan_id=row["id"],
                     item=item["index"], prompt_id=pid)
        for i, (fname, blob) in enumerate(client.collect(pid)):
            dest = rdir / f"{item['index']:02d}-{i}-{fname}"
            atomic_write(dest, blob)
            sha = sha256_file(dest)
            rid = db_mod.insert_render(row["id"], item["index"],
                                       str(dest), sha)
            db_mod.event("render_done", render_id=rid, sha=sha[:12])
            print(f"render #{rid} item {item['index']} -> {dest.name}")
    db_mod.set_plan_status(row["id"], "rendered")


# ---- qc -----------------------------------------------------------------

def cmd_qc(a):
    row = db_mod.get_render(a.render)
    if not row:
        raise SystemExit(f"unknown render id: {a.render}")
    plan = json.loads(db_mod.get_plan(row["plan_id"])["plan_json"])
    spec = _spec_for(db_mod.get_persona(plan["persona"]))
    qc = qc_mod.run_qc(Path(row["path"]), spec)
    db_mod.set_render_status(row["id"], row["status"], qc["status"])
    print(json.dumps(qc, indent=2))


# ---- approve / export -----------------------------------------------------

def cmd_approve(a):
    row = db_mod.get_render(a.render)
    if not row:
        raise SystemExit(f"unknown render id: {a.render}")
    current = sha256_file(Path(row["path"]))
    if current != a.sha256:
        raise SystemExit(f"hash mismatch: file is {current[:16]}… — "
                         "edits invalidate approval; re-run qc")
    if row["qc_status"] not in ("pass", "needs_manual"):
        raise SystemExit(f"qc_status={row['qc_status']} — cannot approve")
    if row["qc_status"] == "needs_manual" and not a.attested:
        raise SystemExit("qc needs_manual — approve with --attested after "
                         "you have eyeballed the artifact")
    db_mod.insert_approval(row["id"], current,
                           a.operator or getpass.getuser())
    db_mod.set_render_status(row["id"], "approved")
    db_mod.event("approved", render_id=row["id"], sha=current[:12])
    print(f"approved render #{row['id']} sha={current[:16]}…")


def cmd_export(a):
    row = db_mod.get_render(a.render)
    if not row:
        raise SystemExit(f"unknown render id: {a.render}")
    sha = db_mod.approved_sha(row["id"])
    if not sha:
        raise SystemExit("render not approved")
    current = sha256_file(Path(row["path"]))
    if current != sha:
        raise SystemExit("artifact changed since approval — refusing export")
    platform = settings().get("publishing", {}).get("platform", "instagram")
    dest = out_dir() / "exports" / platform / Path(row["path"]).name
    if dest.exists():
        raise SystemExit(f"export exists, never overwrite: {dest}")
    atomic_write(dest, Path(row["path"]).read_bytes())
    plan = json.loads(db_mod.get_plan(row["plan_id"])["plan_json"])
    item = plan["items"][row["item_index"]]
    manifest = {"render_id": row["id"], "sha256": sha, "platform": platform,
                "caption": item["caption"], "slot_utc": item["slot_utc"],
                "source": row["path"]}
    atomic_write(dest.with_suffix(".manifest.json"),
                 json.dumps(manifest, indent=2).encode())
    db_mod.insert_post(row["id"], platform, None, None, "exported")
    db_mod.set_render_status(row["id"], "exported")
    print(f"exported render #{row['id']} -> {dest} (+manifest)")


# ---- ig -------------------------------------------------------------------

def cmd_ig_status(_):
    print(json.dumps(ig_mod.status(), indent=2))


def cmd_ig_publish(a):
    row = db_mod.get_render(a.render)
    if not row:
        raise SystemExit(f"unknown render id: {a.render}")
    sha = db_mod.approved_sha(row["id"])
    if not sha or sha256_file(Path(row["path"])) != sha:
        raise SystemExit("render not approved or changed since approval")
    plan = json.loads(db_mod.get_plan(row["plan_id"])["plan_json"])
    spec = _spec_for(db_mod.get_persona(plan["persona"]))
    item = plan["items"][row["item_index"]]
    mtype = "REELS" if Path(row["path"]).suffix.lower() in (".mp4", ".mov") \
        else "IMAGE"
    remote = ig_mod.InstagramPublisher().publish(
        a.media_url, item["caption"], media_type=mtype, spec=spec)
    db_mod.insert_post(row["id"], "instagram", remote, a.media_url,
                       "published")
    db_mod.event("published", render_id=row["id"], remote=remote)
    print(f"published render #{row['id']} -> ig media {remote}")


# ---- status / doctor ------------------------------------------------------

def cmd_status(_):
    plans = db_mod.list_plans()
    renders = db_mod.list_renders()
    by_qc = {}
    for r in renders:
        by_qc[r["qc_status"]] = by_qc.get(r["qc_status"], 0) + 1
    print(json.dumps({
        "personas": len(db_mod.list_personas()),
        "plans": {s: len([p for p in plans if p["status"] == s])
                  for s in {p["status"] for p in plans}},
        "renders": len(renders), "qc": by_qc,
        "publishing": ig_mod.status()["uploads_enabled"],
    }, indent=2))


def cmd_doctor(a):
    ok = True

    def rep(name, good, extra=""):
        nonlocal ok
        ok &= bool(good)
        print(f"{'ok ' if good else 'BAD'}  {name:24s} {extra}")

    rep("python", sys.version_info >= (3, 11), sys.version.split()[0])
    rep("ffmpeg", check("ffmpeg"), check("ffmpeg") or "winget install ffmpeg")
    rep("ffprobe", check("ffprobe"))
    try:
        db_mod.init_db()
        rep("sqlite", True, str(db_mod.db_path()))
    except Exception as e:
        rep("sqlite", False, str(e))
    try:
        s = settings()
        rep("config/settings.yaml", bool(s))
    except Exception as e:
        rep("config/settings.yaml", False, str(e))
    wf = ROOT / settings().get("comfy", {}).get(
        "workflow", "comfy/workflows/persona_flux.json")
    rep("comfy workflow template", wf.exists(), str(wf))
    has_secrets = ig_mod.secret_path().exists()
    print(f"info  secrets/meta.json       "
          f"{'present' if has_secrets else 'absent — manual publishing only'}")
    if a.check_comfy:
        try:
            stats = comfy_mod.ComfyClient().ping()
            vs = stats.get("system", {}).get("comfyui_version", "?")
            rep("comfy server", True, f"comfyui {vs}")
        except Exception as e:
            rep("comfy server", False, str(e))
    try:
        import insightface  # noqa: F401
        rep("face gate (insightface)", True)
    except ImportError:
        rep("face gate (insightface)", True,
            "absent — gate returns needs_manual")
    sys.exit(0 if ok else 1)


# ---- parser -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="instacampaign")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(f=cmd_init)

    ps = sub.add_parser("persona").add_subparsers(dest="sub", required=True)
    c = ps.add_parser("new"); c.add_argument("spec"); c.set_defaults(f=cmd_persona_new)
    ps.add_parser("list").set_defaults(f=cmd_persona_list)
    c = ps.add_parser("validate"); c.add_argument("spec"); c.set_defaults(f=cmd_persona_validate)

    ps = sub.add_parser("plan").add_subparsers(dest="sub", required=True)
    c = ps.add_parser("new")
    c.add_argument("--persona", required=True)
    c.add_argument("--week", required=True)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--posts", type=int, default=None)
    c.set_defaults(f=cmd_plan_new)
    ps.add_parser("list").set_defaults(f=cmd_plan_list)
    c = ps.add_parser("validate"); c.add_argument("plan"); c.set_defaults(f=cmd_plan_validate)

    c = sub.add_parser("generate")
    c.add_argument("--plan", type=int, required=True)
    c.add_argument("--workflow", default=None)
    c.set_defaults(f=cmd_generate)

    c = sub.add_parser("qc"); c.add_argument("--render", type=int, required=True)
    c.set_defaults(f=cmd_qc)

    c = sub.add_parser("approve")
    c.add_argument("--render", type=int, required=True)
    c.add_argument("--sha256", required=True)
    c.add_argument("--operator", default=None)
    c.add_argument("--attested", action="store_true",
                   help="operator eyeballed artifact (required when qc is needs_manual)")
    c.set_defaults(f=cmd_approve)

    c = sub.add_parser("export"); c.add_argument("--render", type=int, required=True)
    c.set_defaults(f=cmd_export)

    ps = sub.add_parser("ig").add_subparsers(dest="sub", required=True)
    ps.add_parser("status").set_defaults(f=cmd_ig_status)
    c = ps.add_parser("publish")
    c.add_argument("--render", type=int, required=True)
    c.add_argument("--media-url", required=True,
                   help="publicly reachable URL of the staged artifact")
    c.set_defaults(f=cmd_ig_publish)

    sub.add_parser("status").set_defaults(f=cmd_status)

    c = sub.add_parser("doctor")
    c.add_argument("--check-comfy", action="store_true")
    c.set_defaults(f=cmd_doctor)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.f(args)
    except (PersonaError, PlanError, comfy_mod.ComfyError,
            ig_mod.PublishError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
