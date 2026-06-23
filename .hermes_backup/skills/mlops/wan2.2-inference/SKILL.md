---
name: wan2.2-inference
description: Wan2.2 text-to-video inference on remote GPU servers (Wan2.2 T2V-A14B, 720P, etc.) — model loading, VAE architecture, multi-transformer sharded loading, and FastAPI server setup.
category: mlops
---

# Wan2.2 Text-to-Video Inference

Serving Wan2.2 T2V models (e.g. `wan2.2_t2v_A14B`) on remote GPU servers via a FastAPI inference server.

## Trigger Conditions
- User asks to run, test, or deploy Wan2.2 (text-to-video) inference
- User references `/data/models/wan2.2_t2v_A14B/` or similar Wan2.2 model path
- Any task involving `WanVideoPipeline`, `AutoencoderKL`, or Wan model conversion

## Architecture Overview

Wan2.2 T2V models have 5 components (not 3):

| Component | Type | Notes |
|---|---|---|
| `scheduler` | `DiffusersScheduler` + `scheduler_config.json` | Instant load from config |
| `text_encoder` | UMT5EncoderModel (Wan-T5, ~5.68B params) | 24 layers, hidden_size=4096, d_kv=512, d_ff=10240, num_heads=8, relative_attention_num_buckets=512 |
| `text_encoder_2` | Not used | Ignore |
| `vae` | `AutoencoderKLWan` | encoder + decoder, ~0.51 GB |
| `transformer` | WanTransformer3DModel — high-noise expert | 6 safetensors shards, ~48.92 GB |
| `transformer_2` | WanTransformer3DModel — low-noise expert | 6 safetensors shards, ~56.38 GB |

Model path on 70.88: `/data/models/wan2.2_t2v_A14B/`

## Critical: `from_pretrained()` is Dangerously Slow

**Direct `safetensors.torch.load_file()` = 0.0 seconds** (memory-mapped, instant).

**`from_pretrained()` on the same model = 30+ minutes** and consumes 100–120GB RAM + 100% CPU while GPU sits at ~1.8GB (empty). This is the primary cause of server startup failures.

**Rule: Never use `from_pretrained()` for model loading.** Load via `safetensors.torch.load_file()` directly.

## Component Loading Strategy

### 1. Scheduler (Instant)
```python
from diffusers import DDPMScheduler
scheduler = DDPMScheduler.from_pretrained(scheduler_path)  # ~instant
```

### 2. Text Encoder — UMT5 SafeTensors Key Remapping Required

**The safetensors use NON-HF naming conventions.** Keys like `blocks.N.attn.q.weight` must be remapped to `encoder.block.N.layer.0.SelfAttention.q.weight` before loading.

Always derive model dimensions from **weight shapes**, NOT from `config.json` — the config often has wrong values (e.g. `d_model=2560, d_ff=2727296` which is clearly a config error).

**Correct UMT5Config parameters** (verified from weight shapes):
```python
from transformers import Umt5Config, Umt5EncoderModel

cfg = Umt5Config(
    is_decoder=False,               # REQUIRED — without this: AttributeError
    hidden_size=4096,               # d_model from weight shapes, NOT config.json
    d_kv=512,
    d_ff=10240,                     # MUST set explicitly; default is 4x=16384 (too large)
    num_hidden_layers=24,           # num_layers in config.json may be wrong
    num_attention_heads=8,         # config.json says 10 — verify from weight shapes
    relative_attention_num_buckets=512,  # config.json says 64 — WRONG
    vocab_size=256384,
)
model = Umt5EncoderModel(cfg)
```

**Key remapping** (required for `load_state_dict` to succeed):
```python
import safetensors.torch, re

def remap_umt5_keys(state_dict):
    """Remap Wan-T5 safetensors keys to HF UMT5EncoderModel key names."""
    new_sd = {}
    for key, val in state_dict.items():
        new_key = key
        # blocks.N.attn.q.weight → encoder.block.N.layer.0.SelfAttention.q.weight
        m = re.match(r'blocks\.(\d+)\.attn\.(q|k|v|o)\.(weight|bias)', key)
        if m:
            layer, attn_type, wt_type = m.group(1), m.group(2), m.group(3)
            attn_map = {'q': 'SelfAttention.q', 'k': 'SelfAttention.k', 'v': 'SelfAttention.v', 'o': 'SelfAttention.o'}
            new_key = f"encoder.block.{layer}.layer.0.{attn_map[attn_type]}.{wt_type}"
        # blocks.N.attn.norm1/2 → layer.0.layer_norm / final_layer_norm
        elif re.match(r'blocks\.\d+\.attn\.norm[12]', key):
            new_key = new_key.replace('.attn.norm1', '.layer.0.layer_norm').replace('.attn.norm2', '.final_layer_norm')
        # blocks.N.pos_embedding.embedding → relative_attention_bias
        elif 'pos_embedding.embedding' in key:
            new_key = new_key.replace('blocks.', 'encoder.').replace('pos_embedding.embedding', 'relative_attention_bias')
        # blocks.N.ffn.* → wi_*/wo
        elif re.match(r'blocks\.\d+\.ffn\.', key):
            new_key = new_key.replace('blocks.', 'encoder.').replace('ffn.gate.0', 'wi_1').replace('ffn.gate.1', 'wi_2').replace('ffn.wo', 'wo')
        new_sd[new_key] = val
    return new_sd

sd = safetensors.torch.load_file(os.path.join(MODEL_PATH, "text_encoder/model.safetensors"))
sd = remap_umt5_keys(sd)
missing, unexpected = model.load_state_dict(sd, strict=False)
# Expected: ~73 layernorm bias keys "missing" — safetensors use a different normalization scheme, this is OK
```

**Verification:**
```python
import safetensors.torch
st = safetensors.torch.safe_open(path, metadata=True)
print(st.metadata())  # keys, shapes, dtypes — use shapes to derive hidden_size, num_heads
```

**Key points:**
- Import `Umt5Config` and `Umt5EncoderModel` from `transformers` (not `optimum.utils`)
- Always set `is_decoder=False` — encoder-only model
- Call `load_state_dict()` immediately after construction, not `from_pretrained()`
- `strict=False` is required — ~73 LayerNorm bias keys are absent from safetensors (different norm scheme)
- config.json values are frequently wrong — always verify against weight shapes

To verify d_model/d_ff/num_layers, inspect safetensors headers:
```python
import safetensors.torch
st = safetensors.torch.safe_open(path, metadata=True)
print(st.metadata())  # keys, shapes, dtypes
```

### 3. VAE — `AutoencoderKLWan` from diffusers ≥ 0.38.0

**The correct class is `AutoencoderKLWan`** from `diffusers.models.autoencoders` (NOT `diffusers.models.autoencoders.vae` and NOT plain `AutoencoderKL`). Verified working import:
```python
from diffusers.models.autoencoders import AutoencoderKLWan  # correct
# AutoencoderKLWan from diffusers.models.autoencoders.vae is WRONG path
# plain AutoencoderKL is for SD-style VAEs, NOT Wan VAE
```

**Do NOT call `AutoencoderKLWan.from_pretrained()` for weight loading** — it is slow. Instead load weights directly:
```python
from diffusers.models.autoencoders import AutoencoderKLWan
import safetensors.torch, torch

# Create model from config only
vae = AutoencoderKLWan.from_pretrained(vae_cfg_path)

# Load weights directly (instant, memory-mapped)
sd = safetensors.torch.load_file(os.path.join(MODEL_PATH, "vae/diffusion_pytorch_model.safetensors"))
for k in sd:
    if sd[k].dtype != torch.bfloat16:
        sd[k] = sd[k].to(dtype=torch.bfloat16)
missing, unexpected = vae.load_state_dict(sd, strict=False)
```

Then verify weights loaded (non-zero sum):
```python
total_params = sum(p.sum().item() for p in vae.parameters())
print(f"VAE param sum: {total_params:.4f}")  # should NOT be ~0
```

If `missing > 0` and `unexpected > 0`, the key names from conversion don't match `AutoencoderKLWan`'s expected keys. See VAE Silent Weight Failure section.

### 4. Transformers (Sharded — Load Directly, Never `from_pretrained()`)

Each transformer has 6 safetensors shards. Loading via `from_pretrained()` takes 10+ minutes per transformer. Always load shards directly:

```python
import safetensors.torch, torch, glob, re
from collections import defaultdict
from diffusers.models.transformers.transformer_wan import WanTransformer3DModel

def load_sd_from_shards(dir_path, dtype=torch.bfloat16):
    shard_files = sorted(glob.glob(os.path.join(dir_path, "diffusion_pytorch_model-*-of-*.safetensors")))
    if not shard_files:
        single = os.path.join(dir_path, "diffusion_pytorch_model.safetensors")
        sd = safetensors.torch.load_file(single)
        for k in sd:
            if sd[k].dtype != dtype: sd[k] = sd[k].to(dtype=dtype)
        return sd
    shards = defaultdict(dict)
    for sf in shard_files:
        m = re.search(r"-(\d+)-of-(\d+)", os.path.basename(sf))
        if not m: continue
        shards[int(m.group(1))] = sf
    sd = {}
    for idx in sorted(shards):
        with safetensors.torch.safe_open(shards[idx]) as f:
            for k in f.keys():
                v = f.get_tensor(k)
                if v.dtype != dtype: v = v.to(dtype=dtype)
                sd[k] = v
    return sd

# Usage:
cfg_path = os.path.join(MODEL_PATH, "transformer")
model = WanTransformer3DModel.from_pretrained(cfg_path)
sd = load_sd_from_shards(os.path.join(MODEL_PATH, "transformer"))
missing, unexpected = model.load_state_dict(sd, strict=False)
# Fast: ~5-10s per shard instead of 10+ minutes
```

## Known Issues

### UMT5 `is_decoder` AttributeError (Blocked Server Startup)
- **Symptom**: `AttributeError: 'PreTrainedConfig' object has no attribute 'is_decoder'` during `Umt5EncoderModel(cfg)` or `from_pretrained()`
- **Root cause**: `Umt5Config` must have `is_decoder=False` — the model architecture checks this attribute; missing value causes AttributeError
- **Fix**: Always set `is_decoder=False` in `Umt5Config`
- **Also check**: `num_attention_heads=8` (not 10), `relative_attention_num_buckets=512` (not 64) — verify against weight shapes

### NVFP4 Quantized Model — Critical Limitations

`nvidia/Wan2.2-T2V-A14B-Diffusers-NVFP4` contains **packed NF4 uint8 weights**. Transformer weights are stored as uint8 with shape `[5120, 2560]` = 5120×5120×4bit (packed NF4). Loading without dequantization gives shape mismatch errors:

```
blocks.10.attn1.to_k.weight expected shape torch.Size([5120, 5120]), but got torch.Size([5120, 2560])
```

**NVFP4 dequantization requires `modelopt`** — the full NVIDIA modelopt package (not on PyPI; installable from NVIDIA NGC or GitHub). The following exist in the venv but are insufficient alone:
- `diffusers.quantizers.modelopt.NVIDIAModelOptQuantizer`
- `compressed_tensors.NVFP4PackedCompressor` (but requires modelopt core to function)

**Workaround: Use the original fp16 model at `/data/models/wan2.2_t2v_A14B/`** (132GB, non-diffusers format) — loads directly without modelopt. Structure:
- `text_encoder/model.safetensors` — Umt5EncoderModel, hidden_size=2560
- `high_noise_model/` and `low_noise_model/` — 6 safetensors shards each (~46GB per transformer)
- VAE: Wan2.1_VAE.pth

When writing inference code for the fp16 model, use `WanPipeline.from_pretrained(MODEL_PATH, class_name="WanPipeline")` and load components individually via `safetensors.torch.load_file()` + `load_state_dict()` as described above.

**Always prefer the fp16 model for new deployments** — the NVFP4 model requires a separate modelopt installation that is non-trivial to configure.

### VAE Silent Weight Failure
- **Symptom**: Decoder has "newly initialized" layers after loading; `missing > 0` and `unexpected > 0` from `load_state_dict`
- **Root cause**: Key name mismatch (`downsamples` vs `down_blocks`, `upsamples` vs `up_blocks`)
- **Impact**: VAE produces garbage/no output — decoder weights are random
- **Fix**: Remap key names during conversion. Verify post-load: `sum(p.sum() for p in model.parameters())` should be non-zero
- **Workaround**: Load with `strict=False`, check `missing/unexpected` counts, warn if decoder layers are affected

### Slow Model Loading (`from_pretrained`)
- **Symptom**: Server hangs during startup, GPU at 1.8GB for minutes; process consumes 100-120GB RAM + 100% CPU
- **Root cause**: `from_pretrained()` hooks load entire model into CPU RAM before copying to GPU; safetensors are memory-mapped and instant
- **Fix**: Replace all `from_pretrained()` loads with `safetensors.torch.load_file()` + `model.load_state_dict(sd)` (see Component Loading Strategy above)

## Inference Request Format

```bash
curl -X POST http://localhost:7860/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cat playing piano in a moonlit room",
    "num_frames": 49,
    "height": 480,
    "width": 720,
    "num_inference_steps": 20
  }'
```

Expected response: PNG image (first frame preview) or error JSON.

## FastAPI Server Patterns

### Lifespan (Not `@app.on_event`)
`@app.on_event("startup")` is deprecated. Use lifespan context manager instead:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: load models here
    await load_all_models()
    yield
    # shutdown: cleanup here
    pass

app = FastAPI(lifespan=lifespan)
```

### Remote Process Restart — Requires User Consent
When deploying to a remote server (e.g. 70.88), `pkill` / `kill -9` commands targeting the server process **require user consent** — the terminal tool will block with "User denied this command". 

**Workflow**: Write the new server script → upload via `base64 | ssh` → **ask user to manually run `pkill -f wan22_t2v_server.py`** on 70.88 → then start new server. Do not loop retrying kill commands.

### Server Startup Log Check
After starting, check the log:
```bash
ssh jianliu@10.10.70.88 "tail -30 /tmp/wan22_t2v_server.log"
```
If "ALL MODELS LOADED — ready to serve!" appears, server is up on port 7860.

## Files

- `references/wan22_server.md` — Full FastAPI server implementation (correct imports for diffusers 0.38.0)
- `references/wan22_umt5_text_encoder.md` — UMT5Config parameters, key remapping (if needed), common import fixes
- `references/wan22_nvfp4_vs_fp16.md` — NVFP4 quantized vs fp16 model variant decision guide (modelopt requirement, fp16 workaround)