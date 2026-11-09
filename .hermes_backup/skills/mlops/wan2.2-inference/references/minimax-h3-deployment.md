# MiniMax-H3 — Omni-Modal Video+Audio Model Deployment

MiniMax-H3 is an omni-modal (text+image+video+audio → video+audio) generative
system from MiniMax. Repo: `MiniMaxAI/MiniMax-H3` on HuggingFace. This is a
**different class of video model than Wan2.2** (omni-modal, native stereo audio,
video editing via references) but served on the same fleet / same infra
families (SGLang / vLLM / diffusers).

## The repo hosts THREE weight sets — which to download

Verified by inspecting `https://huggingface.co/api/models/MiniMaxAI/MiniMax-H3/tree/main`:

| Weight set | Class | Size | Role |
|---|---|---|---|
| `FL2VA/transformer/` (13 shards) | `MiniMaxH3DiTModel` | 144 GB total family | **FL2VA checkpoint** → serves `t2va` + `fl2va` |
| `Ref2VA/transformer/` (13 shards) | `MiniMaxH3DiTModel` | 144 GB total family | **Ref2VA checkpoint** → serves `ref2va` |
| top-level `transformer/` (14 shards) | `MiniMaxH3Transformer3DModel` | 66 GB | Modular/diffusers main transformer |
| top-level `transformer_ref/` (14 shards) | `MiniMaxH3Transformer3DModel` | 66 GB | Modular reference transformer |

Key insight: **the 3 "(+) " weights are two task checkpoints (FL2VA, Ref2VA)
plus a separate modular diffusers format — not co-dependent stages.**

## FL2VA vs Ref2VA — the two real variants

| | FL2VA | Ref2VA |
|---|---|---|
| Meaning | First/Last **Frame** to Audio-Video | **Reference** to Audio-Video |
| Tasks | `t2va`, `fl2va` | `ref2va` |
| Input | text; optional first/last keyframe image | text + reference image/video/audio |
| Use | start/end-frame control, pure text-to-video | video editing: preserve identity, swap dialogue, keep/reference audio |

Selected at runtime via `--model-variant fl2va|ref2va` and the `task` field.

## Download scoping — you do NOT need all weights

For SGLang/vLLM the official download (from the README) is exactly:

```bash
hf download MiniMaxAI/MiniMax-H3 --include "model_index.json" "FL2VA/*" "Ref2VA/*" --local-dir MiniMax-H3
# or single family:
hf download MiniMaxAI/MiniMax-H3 --include "model_index.json" "FL2VA/*" --local-dir MiniMax-H3
```

Each of `FL2VA/` and `Ref2VA/` is **self-contained** (transformer + processor +
tokenizer + text_encoder + visual VAE + audio VAE). Root `transformer/` +
`transformer_ref/` (~132 GB) are ONLY used by the diffusers modular pipeline
(`MiniMaxH3ModularPipeline.from_pretrained(...)`) — skip them for SGLang/vLLM.

- Both families: ~288 GB. Single family: ~144 GB.
- Keep root `model_index.json` (~3 KB) — it's the repo entry / required include.
- diffusers users never download manually; the pipeline auto-fetches.

## SGLang deployment (official)

```bash
# FL2VA / T2VA — port 30010
sglang serve --model-path MiniMaxAI/MiniMax-H3 --num-gpus 4 --ulysses-degree 4 \
  --performance-mode speed --host 0.0.0.0 --port 30010 --model-variant fl2va

# Ref2VA — port 30011
sglang serve --model-path MiniMaxAI/MiniMax-H3 --num-gpus 4 --ulysses-degree 4 \
  --performance-mode speed --host 0.0.0.0 --port 30011 --model-variant ref2va
```

## Request payloads — FL2VA vs Ref2VA

Both POST to `/v1/videos`, differ in `task` and `conditions`, then
`GET /v1/videos/$id` for status → `GET /v1/videos/$id/content` for mp4.

**FL2VA** (`task:"fl2va"`) — conditions = keyframe image(s):
```json
{ "task": "fl2va", "prompt": "<H3-Context-IR prompt>",
  "conditions": [ { "type": "image", "uri": "https://…/first_frame.png",
                    "role": "keyframe", "frame_index": 0 } ],
  "target": { "short_edge": 768, "aspect_ratio": "auto", "duration_seconds": 8 },
  "seed": 0 }
```
`t2va` = same but `task:"t2va"` and empty conditions.

**Ref2VA** (`task:"ref2va"`) — conditions = reference video + audio:
```json
{ "task": "ref2va", "prompt": "<subject_definitions/summary/retention_analysis…>",
  "conditions": [
     { "type": "video", "uri": "https://…/source.mp4", "role": "reference" },
     { "type": "audio", "uri": "https://…/voice_ref.mp3", "role": "reference" } ],
  "target": { "short_edge": 768, "aspect_ratio": "auto", "duration_seconds": 5 },
  "seed": 0 }
```

Prompt style differs by variant:
- FL2VA/T2VA: `integrated_multimodal_description / overall_soundscape / non_diegetic_music`
- Ref2VA: `subject_definitions / summary / retention_analysis / detailed_description / overall_soundscape / non_diegetic_music` — references `<Video 1>` `<Audio 1>` flags.

## vLLM — only reading the weights it needs under parallelism

Yes, vLLM supports this. Sourced from current vllm source:
- **Default `load_format="safetensors"`**: each TP rank loads only its own slice
  of each sharded tensor. Uses `filter_duplicate_safetensors_files` +
  `filter_files_not_needed_for_inference` — whole weight files a rank doesn't
  need (e.g. EP experts) are skipped. Saves RAM/load time, not disk.
- **`--load-format sharded_state`** → `ShardedStateLoader`: each rank reads ONLY
  its own shard files `model-rank-{rank}-part-{part}.safetensors`
  (DEFAULT_PATTERN). Literally "only reads what it needs." Requires pre-sharded
  checkpoint via `examples/features/sharded_state/save_sharded_state_offline.py`.
- **`--enable-ep-weight-filter`**: for MoE models, skips non-local expert
  tensors per EP rank.

For MiniMax-H3: it's a **dense 50-layer DiT** (no MoE), so TP slicing is
automatic (`--tensor-parallel-size N`); EP filter is irrelevant. `sharded_state`
gives the strict per-rank behavior but needs pre-sharding.
