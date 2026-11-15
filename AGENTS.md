# InstaCampaign engineering rules

Adapted from Naminal Hub (`~/Documents/AnimalVideoPipeline/AGENTS.md`) and
Resting Beat (`~/Documents/OBESession/AGENTS.md`).

- Root package `src/instacampaign`; `config/` holds safe local defaults;
  `docs/` covers architecture, content policy, monetization and the Windows
  handoff. `comfy/` holds ComfyUI API-format workflow templates.
- `uv sync --group dev`; `uv run --group dev pytest`;
  `uv run python main.py doctor`.
- SQLite is authoritative and append-only: personas, assets, plans, renders,
  approvals, posts and events are never silently discarded or rewritten.
- Content ceiling is SFW (PG-13). Explicit or nude generation and posting is
  permanently out of scope. The SFW gate fails closed: when the classifier is
  unavailable, output requires operator attestation, never auto-approval.
- Personas are synthetic and disclosed. `disclosure` is required in every
  persona spec and on the Instagram profile; Meta's AI label is applied where
  required. Never imitate a real or identifiable person — no deepfake
  tooling. Face consistency binds only the persona's own generated
  reference sheet.
- No automated DM/chat monetization tooling. Deceptive paid conversation is
  fraud; it is out of scope regardless of revenue potential.
- Publishing is dormant by default: the operator uploads manually from local
  export packages. The `ig` adapter refuses unless `publishing
  .uploads_enabled` is true, `secrets/meta.json` exists (allowlisted keys
  only, gitignored, mode-600) and the persona carries disclosure.
- One heavy job at a time; generation jobs are serial. Subprocesses use argv
  arrays and bounded timeouts; output files are written atomically
  (tmp + rename). ComfyUI is a local server only (`127.0.0.1:8188`).
- Approval is hash-bound: a render edit invalidates approval; exact SHA-256
  is required at approval and re-verified at export.
- Definition of done: offline tests pass, real ffprobe validation for reel
  MP4s, `qc.json` artifact emitted per render.
