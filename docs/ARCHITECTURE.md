# Architecture

## Boundaries and flow

```
persona spec (validated, disclosed, SFW-capped)
  -> seeded weekly plan (deterministic; hash-bound to persona spec hash)
  -> ComfyUI API submission (serial; local server only)
  -> artifact + qc.json (media spec / sfw / face-similarity gates)
  -> hash-bound operator approval (needs_manual requires --attested)
  -> local per-platform export package (never overwrites)
  -> [dormant] Instagram Graph API publish
  -> [later] read-only Insights ingestion
```

SQLite is authoritative. Plans bind `persona_sha` — editing a persona spec
after planning makes `plan validate` fail closed, same contract as
Naminal's footage budget and Resting Beat's plan hash.

## Sibling-project reuse map

| Pattern | Source | Decision |
| --- | --- | --- |
| append-only ledger + event log | animal_pipeline core/db | adapted; fresh schema |
| seeded deterministic plan + sha256 | restingbeat plans | adapted; week-scoped |
| argv ffmpeg + ffprobe QC + atomic writes | animal_pipeline media/editor | adapted; reel spec gates |
| hash-bound approval, no-overwrite export | both | kept verbatim semantics |
| allowlisted `secrets/` credential migration | animal_pipeline google_auth | adapted to `secrets/meta.json` |
| dormant upload adapter + verified identity | animal_pipeline youtube | adapted to `ig` Graph API |
| evidence/species/facts/TTS stack | animal_pipeline | dropped — no narration |
| procedural audio | restingbeat | dropped |

## New work unique to this project

- `comfy.py`: workflow-template submission against local ComfyUI
  (`{{PROMPT}}`/`{{NEGATIVE}}`/`{{SEED}}`/`{{PREFIX}}` tokens).
- `qc.face_gate`: ArcFace embedding similarity vs the persona's own
  generated reference sheet — replaces "species matching" as the identity
  QC. Optional `face` extra; absent => needs_manual.
- `qc.sfw_gate`: NSFW classifier ceiling — replaces nothing; it's the
  enforcement of the content policy ceiling. Optional `nsfw` extra;
  absent => needs_manual.

## Milestones

A. Schema, persona validation, seeded planner, offline tests. **Done.**
B. ComfyUI render loop + qc gates + approval/export on Windows.
C. Reference-sheet bootstrap tooling + batch review UI (optional).
D. Dormant IG publish behind gate; read-only insights; weekly report.
