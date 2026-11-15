# InstaCampaign

Synthetic, disclosed-AI persona pipeline: persona spec → seeded content plan
→ ComfyUI generation → QC gates → hash-bound approval → local export →
(dormant) Instagram Graph API publishing → read-only analytics.

Built on the render/QC/approval spine of `AnimalVideoPipeline` and
`OBESession`. SFW-only by design — see `docs/CONTENT_POLICY.md`.

**Development target: Windows + ComfyUI on Shadow PC (28 GB RAM, 20 GB
VRAM, Flux.1-dev).** Pickup instructions: `docs/HANDOFF.md`.

## Quickstart

```sh
uv sync --group dev
uv run python main.py doctor
uv run python main.py init
uv run python main.py persona validate config/personas/example.persona.yaml
uv run python main.py plan new --persona example --week 2026-W47 --seed 7
```

Generation requires a running ComfyUI (`--listen 127.0.0.1 --port 8188`)
and an API-format workflow at `config.settings.yaml:comfy.workflow`.
