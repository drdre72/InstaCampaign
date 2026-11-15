# ComfyUI workflow templates

`generate` loads the template named by `config/settings.yaml:comfy.workflow`
(default `persona_flux.json`) and string-replaces four tokens before
submitting to the local ComfyUI API:

| Token | Where it lands in the workflow |
| --- | --- |
| `{{PROMPT}}` | positive CLIPTextEncode `text` value |
| `{{NEGATIVE}}` | negative CLIPTextEncode `text` value |
| `{{SEED}}` | KSampler `seed` (bare number — no quotes) |
| `{{PREFIX}}` | SaveImage `filename_prefix` |

## Building `persona_flux.json` on the Shadow PC (20 GB VRAM)

1. Nodes needed (install via ComfyUI-Manager):
   - Flux.1-dev checkpoint: `flux1-dev-fp8.safetensors` **or**
     `flux1-dev-Q8_0.gguf` + `ComfyUI-GGUF` node pack
   - Identity: `ComfyUI-PuLID-Flux` **or** `ComfyUI_InstantID` (+ InsightFace
     dependency) — binds the persona reference sheet into every render
   - Base graph: Load Checkpoint → PuLID/InstantID (reference image) →
     CLIPTextEncode (positive) → CLIPTextEncode (negative) → KSampler →
     VAE Decode → SaveImage
2. Suggested starting params (Flux): 832×1216 (~4:5 IG portrait),
   28 steps, guidance 3.5.
3. Save via **Settings → enable Dev mode options → "Save (API Format)"**.
4. Edit the exported JSON: swap the four runtime values for the tokens
   above, commit as `persona_flux.json`.
5. Sanity: `uv run python main.py generate --plan <id>` with a 1-post plan.

Keep the human-editable `.json` (non-API format) out of the repo — it
contains node-layout cruft that churns diffs.
