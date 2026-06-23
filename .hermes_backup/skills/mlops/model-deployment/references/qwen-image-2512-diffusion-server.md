# Qwen-Image-2512 Diffusion Server — Deployment Reference

## Model Identity

| Property | Value |
|----------|-------|
| **HF repo** | `Qwen/Qwen-Image-2512` |
| **Local path** | `/data/models/qwen_image_2512/` on 10.10.70.88 |
| **Model type** | `QwenImagePipeline` — **diffusion image generation**, NOT a text LLM |
| **Transformer** | `QwenImageTransformer2DModel` (60 layers, diffusion transformer) |
| **VAE** | `AutoencoderKL` |
| **Text encoder** | `Qwen2_5_VLForConditionalGeneration` (vision-language encoder) |
| **Scheduler** | `FlowMatchEulerDiscreteScheduler` |
| **Downloaded** | 2026-06-03 (via hf-mirror.com, setsid, PID stable ~3h) |
| **Size** | ~117 GB |
| **Hardware** | 10.10.70.88: 8× RTX 5090 32GB |

## vLLM Cannot Serve This — Critical Distinction

**vLLM only serves causal language models** (text generation, chat, completion).
Qwen-Image-2512 is a **diffusion image generation pipeline** — it:
- Takes a text prompt + optional image → generates a new image
- Uses denoising diffusion in latent space (not next-token prediction)
- Contains a 60-layer diffusion transformer, VAE decoder, and vision text encoder
- Is fundamentally incompatible with vLLM's model architecture assumptions

**The correct stack: `diffusers` + `FastAPI` + `uvicorn`**

## Installation on the Server

The vLLM venv already has most deps. Only `diffusers` needed installing:

```bash
/data/venvs/vllm-ds4/bin/pip install diffusers --timeout 300
# Result: diffusers 0.38.0 installed
# Already present: transformers, safetensors, pillow, fastapi, accelerate 1.13.0
```

## Server Script

`/data/scripts/qwen_image_server.py` on 10.10.70.88 (persistent location — not `/tmp/` which is volatile):

```python
import os, io, base64, torch
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from diffusers import DiffusionPipeline

MODEL_PATH = "/data/models/qwen_image_2512"
app = FastAPI(title="Qwen-Image-2512 API")
pipe = None

class GenerateRequest(BaseModel):
    prompt: str = Field(...)
    negative_prompt: str = Field("")
    num_inference_steps: int = Field(50, ge=1, le=200)
    true_cfg_scale: float = Field(4.0, ge=1.0, le=20.0)
    height: int = Field(1024, ge=256, le=2048)
    width: int = Field(1024, ge=256, le=2048)
    seed: Optional[int] = Field(None)

@app.on_event("startup")
def startup():
    global pipe
    pipe = DiffusionPipeline.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_sequential_cpu_offload()
    pipe.set_progress_bar_config(disable=True)
    print("Loaded with sequential CPU offload.")

@app.get("/")
def health(): return {"status": "ok"}

@app.get("/info")
def info():
    mem = torch.cuda.mem_get_info() if torch.cuda.is_available() else (0, 0)
    return {"model": "Qwen-Image-2512", "gpu_free_gb": round(mem[0]/1e9, 1)}

@app.post("/generate")
def generate(req: GenerateRequest):
    global pipe
    if not pipe: return JSONResponse({"error": "not loaded"}, status_code=503)
    gen = torch.Generator("cuda").manual_seed(req.seed) if req.seed else None
    result = pipe(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt or None,
        width=req.width, height=req.height,
        num_inference_steps=req.num_inference_steps,
        true_cfg_scale=req.true_cfg_scale,
        generator=gen,
    )
    buf = io.BytesIO()
    result.images[0].save(buf, format="PNG")
    return {"image_base64": base64.b64encode(buf.getvalue()).decode(), "format": "png"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", workers=1)
```

## Start Command

```bash
ssh jianliu@10.10.70.88 "source ~/.bashrc && setsid /data/venvs/vllm-ds4/bin/python3 /data/scripts/qwen_image_server.py </dev/null >/tmp/qwen_image_server.log 2>&1 &"
# Log: /tmp/qwen_image_server.log
# PID: check with: ps aux | grep qwen_image_server | grep -v grep
# Server script: /data/scripts/qwen_image_server.py (persisted, not in /tmp/)
```

## API Usage

```bash
# Health
curl http://10.10.70.88:8000/
# Info
curl http://10.10.70.88:8000/info

# Generate (via JSON file to avoid curl escaping issues with complex prompts)
cat > /tmp/test_req.json << 'EOF'
{"prompt":"A cyberpunk city at sunset","num_inference_steps":20,"true_cfg_scale":4.0,"height":512,"width":512,"seed":42}
EOF
curl -X POST http://10.10.70.88:8000/generate -H 'Content-Type: application/json' -d @/tmp/test_req.json

# To enable CFG guidance (true_cfg_scale is NOT ignored):
cat > /tmp/test_req.json << 'EOF'
{"prompt":"A cyberpunk city at sunset","negative_prompt":"blurry, low quality, distorted","num_inference_steps":20,"true_cfg_scale":4.0,"height":512,"width":512,"seed":42}
EOF
# Without negative_prompt, true_cfg_scale is silently ignored (only warning in log).
```

## Notion API Integration (File Recording)

When recording results to Notion pages via the API:
- **Python files**: NOT directly uploadable — Notion's File Upload API only accepts specific content types. Embed Python as a `code` block instead (max 2000 chars per block; split longer scripts into two blocks with a note about full path).
- **Code block limit**: 2000 characters per block. For scripts longer than 2000 chars, split: first block + paragraph note referencing full path.
- **Callout emoji**: Must be valid Unicode emoji strings — `⚠️` ✅, `WARNING` ❌ (HTTP 400).
- **Table blocks**: Require `table_width` field set to the number of columns.
- **File blocks**: `file://` local paths are not valid — only `https://` external URLs. For local files, record the path in a paragraph/callout block instead.
- **PATCH /pages/{id}/markdown**: Not a valid endpoint. Use `PATCH /v1/blocks/{page_id}/children` with block JSON for appending content. Use `PATCH /v1/pages/{page_id}/markdown` (the `/markdown` suffix endpoint) for markdown body replacement.
```

## Performance (Measured)

| Resolution | Steps | Time | Offload strategy |
|-----------|-------|------|-----------------|
| 512×512 | 20 | ~100s | sequential_cpu_offload |
| 1024×1024 | 20 | ~400s | sequential_cpu_offload |
| 1024×1024 | 50 | ~1000s | sequential_cpu_offload |
| 512×512 | 20 | ~300s | **device_map="balanced"** (8 GPUs, SLOWER due to NCCL) |

## GPU Offloading: Key Finding

### Sequential CPU Offload (BEST for this model)
```python
pipe.enable_sequential_cpu_offload()
```
- Loads full model in bfloat16 into GPU 0, then moves each component to GPU as needed
- GPU 0 uses ~1.8 GB during inference; other GPUs ~0 GB
- **~100s for 512×512 @ 20 steps** — faster than balanced
- Suitable for models too large for a single GPU

### device_map="balanced" (AVOID for diffusion models)
```python
pipe = DiffusionPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16, device_map="balanced")
```
- Distributes model components across all 8 GPUs via accelerate
- BUT: `device_map="auto"` NOT supported in older accelerate (error: `auto not supported. Supported strategies are: balanced, cuda, cpu`)
- `device_map="balanced"` causes **~300s for 512×512 @ 20 steps** — 3× slower
- Root cause: diffusion inference has frequent attention all-gather operations between transformer layers; NCCL communication across 8 GPUs dominates runtime

### Full GPU (NOT POSSIBLE here)
- Transformer alone ≈ 26 GB in bfloat16 — exceeds single RTX 5090 32GB by a large margin
- Awaiting: AWQ/GNFQ quantization of the transformer would reduce memory by 4–8× and enable full-GPU inference

## Known Issues

### tqdm error: "Unknown argument(s): {'enabled': False}"
- `pipe.set_progress_bar_config(enabled=False)` — wrong kwarg
- Fix: `pipe.set_progress_bar_config(disable=True)`

### CFG warning: "true_cfg_scale is passed, but classifier-free guidance is not enabled since no negative_prompt is provided"
- Harmless — just means CFG scale is ignored if no negative_prompt
- To enable CFG: pass a non-empty `negative_prompt` string

### CUDA OOM at startup (on GPU 0)
- Error: `torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 72.00 MiB. GPU 0 has a total capacity of 31.36 GiB of which 66.19 MiB is free`
- Cause: `pipe = pipe.to("cuda")` after loading tries to move the full model to GPU, but it was already partially on GPU from a prior process's cache
- Fix: `pipe.enable_sequential_cpu_offload()` — never `.to("cuda")` for large diffusion models

## Remote File Transfer Pattern

When writing Python files to remote servers, heredoc escaping becomes unreliable. Use base64 encoding:

```bash
# Locally:
python3 -c "import base64; open('/tmp/f_b64.txt','w').write(base64.b64encode(open('/tmp/qwen_image_server.py').read()).decode())"

# Remotely:
B64=$(cat /tmp/f_b64.txt) && ssh jianliu@10.10.70.88 "echo '$B64' | base64 -d > /tmp/qwen_image_server.py"
```

## torch.compile + sequential_cpu_offload Fix (Critical)

**Problem**: `torch.compile` (PyTorch 2.x JIT) is incompatible with `enable_sequential_cpu_offload()`. The `torch._dynamo` compiler tries to trace the model's forward pass at runtime, but sequential offload dynamically moves modules to GPU inside the loop — triggering a `torch._dynamo.config` error.

**Fix**: Disable dynamo before loading the pipeline:
```python
import torch
torch._dynamo.config.disable = True   # MUST be set BEFORE from_pretrained

from diffusers import DiffusionPipeline
pipe = DiffusionPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()
```
Without this line, startup will fail or hang on models that trigger dynamo tracing.

## Benchmark Results (2026-06-08)

Hardware: 10.10.70.88 — 8× RTX 5090 32GB, single GPU used by sequential offload
Server: `qwen_image_server_v2.py` with `torch._dynamo.config.disable = True`
Resolution: 512×512 | Steps: 20 | Prompt: dragon/fantasy kingdom | CFG: 4.0 | Seed: 123

| Run | Time | Image size |
|------|------|------------|
| Warmup | 190.9s | 384KB |
| Run 1  | 191.9s | 384KB |
| Run 2  | 192.8s | 384KB |
| Run 3  | 191.5s | 384KB |
| **Avg** | **192.1s** | — |
| **Throughput** | **0.31 img/min** | — |

**Per-step breakdown** (from prior session, 512×512, cold start):
- 1 step: ~7s
- 5 steps: ~22s  
- 10 steps: ~52s
- 20 steps: ~91s (warm start)
- 20 steps: ~192s (benchmark avg, warmup overhead included)

**Bottleneck**: `sequential_cpu_offload()` reloads the full 57GB model CPU→GPU on every diffusion step (~4.5s/step overhead). No xformers or flash_attn installed — only base PyTorch attention.

## Alternative: enable_model_cpu_offload()

`pipe.enable_model_cpu_offload()` is smarter than `enable_sequential_cpu_offload()`:
- Moves each module to GPU only when needed, then back to CPU — no full reload per step
- Expected ~20% faster than sequential offload
- Trade-off: slightly higher peak GPU memory usage

```python
import torch
torch._dynamo.config.disable = True
pipe = DiffusionPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16)
pipe.enable_model_cpu_offload()   # replace enable_sequential_cpu_offload()
```

## Future Optimizations

1. **AWQ/GNFQ quantization** of `transformer/` — would reduce from 26GB to ~4-6GB per GPU, enabling full-GPU inference with 8×TP
2. **Multi-node diffusion serving** — spread transformer layers across multiple 8-GPU servers
3. **vLLM multimodal** — if vLLM eventually supports diffusion/multimodal pipelines, this would enable faster batched serving with proper KV cache
4. **Torch compile** — `pipe.transformer = torch.compile(pipe.transformer, mode="reduce-overhead")` could speed up the diffusion loop (~20-40% improvement). Must be applied AFTER enabling offload, not before, and only on components that stay on GPU throughout inference.