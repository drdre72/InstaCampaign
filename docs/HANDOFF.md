# Windows / Shadow PC pickup

This repo was scaffolded on macOS; development continues on a **Shadow PC
(Windows, 28 GB RAM, 20 GB VRAM)** running **ComfyUI** as the generation
backend. Everything below assumes that machine.

## 1. Prerequisites (Windows)

```powershell
winget install Git.Git astral-sh.uv Gyan.FFmpeg
git clone https://github.com/drdre72/InstaCampaign
cd InstaCampaign
uv sync --group dev                # add: --extra face --extra nsfw
uv run python main.py doctor
```

`--extra face` installs insightface+onnxruntime (face-consistency QC);
`--extra nsfw` installs the SFW classifier. Both optional — absent gates
return `needs_manual` and require `--attested` at approval (fail-closed,
same as sibling pipelines).

## 2. ComfyUI

- Install **ComfyUI portable** + **ComfyUI-Manager**.
- **Checkpoint at 20 GB VRAM: Flux.1-dev** — `flux1-dev-fp8.safetensors`
  (~12 GB) or `flux1-dev-Q8_0.gguf` via ComfyUI-GGUF. Both fit with
  headroom; fp16 is possible but tight with identity adapters. SDXL is the
  cheap fallback for tests.
- **Identity nodes (the persona crux):** `ComfyUI-PuLID-Flux` or
  `ComfyUI_InstantID` — face-lock against the persona reference sheet.
  Requires InsightFace (`insightface`, `onnxruntime-gpu` on the Shadow).
- Run headless: `python main.py --listen 127.0.0.1 --port 8188`
  (or the portable `run_nvidia_gpu.bat` with those args).
- Verify: `uv run python main.py doctor --check-comfy`.

## 3. Reference face sheet (per persona — do once)

1. In ComfyUI, generate a base identity: one strong front-facing headshot
   from the persona's `style_prompt`.
2. Build 4–12 reference images of *that same face* (angles/lighting) using
   PuLID/InstantID with the first shot as reference.
3. Save to `assets/personas/<name>/reference/` (gitignored).
4. Every later generation run uses the same sheet; `qc face` rejects drift.

## 4. Workflow template

The pipeline needs an **API-format** workflow at
`comfy/workflows/persona_flux.json`:

1. In ComfyUI build the graph: Flux checkpoint → PuLID/InstantID (reference
   sheet) → CLIPTextEncode positive/negative → KSampler → SaveImage.
2. Settings → enable **Dev mode options** → toolbar **"Save (API Format)"**.
3. Edit the JSON: replace the positive-prompt text with `{{PROMPT}}`,
   negative with `{{NEGATIVE}}`, sampler `seed` value with `{{SEED}}` (bare
   number, no quotes), SaveImage `filename_prefix` with `{{PREFIX}}`.
4. Commit it. `comfy/workflows/README.md` has the full checklist.

## 5. Run loop

```powershell
uv run python main.py persona new config/personas/aria.persona.yaml
uv run python main.py plan new --persona aria --week 2026-W47 --seed 7
uv run python main.py generate --plan 1        # serial, idempotent
uv run python main.py qc --render 1            # writes qc.json
uv run python main.py approve --render 1 --sha256 <sha> [--attested]
uv run python main.py export --render 1        # -> output/exports/instagram/
```

Uploads stay manual until the dormant `ig publish` gate is enabled — see
`src/instacampaign/ig.py` docstring for what Meta setup that needs
(Professional account, dev-mode Meta app, `secrets/meta.json`, public
media URL via a bucket/static host).

## 6. Known differences from the Mac pipelines

- No VideoToolbox — `media.assemble_reel` uses libx264 everywhere.
- No Kokoro/mlx — no TTS at all; captions are plan-generated.
- ComfyUI replaces Ollama as the local model server; LLM caption
  generation is deferred (optional Ollama on Windows later).
- Reels are optional: stills posts/carousels are enough to start; image-to-
  video (Wan 2.2 / LTX-Video GGUF) fits in 20 GB later.
