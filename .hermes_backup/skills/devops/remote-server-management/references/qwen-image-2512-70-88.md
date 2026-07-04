# qwen_image_2512 on 10.10.70.88 — Inference Server

## Model Location
- Path: `/data/models/qwen_image_2512/` on 10.10.70.88
- Size: 54GB
- Model type: Qwen Image (DiffusionPipeline, text-to-image)
- Server script: `/tmp/qwen_image_server.py` (FastAPI + uvicorn on port 8000)

## Server Status (as of 2026-06-08)
- Running on 70.88 (PID via `pgrep -fa qwen_image_server`)
- Script location: `/tmp/qwen_image_server.py` (NOT in `/data/models/` — files there are owned by rapidsdb)
- Offload mode: `enable_sequential_cpu_offload()` — CPU-based, ~4-5s/step on RTX 5090
- Dynamo disabled (`torch._dynamo.config.disable = True`) to avoid crash
- Model loading at startup takes ~30-60s — `/health` returns 404 until fully loaded
- **Requires `GET /health` endpoint** — benchmark clients (qwen_benchmark.py) check this first. The `health()` function was originally mapped to `GET /`, requiring a patch to add `GET /health`.

## CRITICAL BUG: torch dynamo + sequential_cpu_offload Incompatibility

**Full error:**
```
RuntimeError: Tensor on device meta is not on the expected device cuda:0!
```

**Root cause:** PyTorch 2.x's `torch.compile()` (dynamo) is enabled by default in PyTorch 2.11+ (cuda 13.0). When used with `enable_sequential_cpu_offload()`, dynamo wraps forward functions with a compiler that tracks tensor device state via `fake_tensor` / meta tensors. Sequential CPU offload moves actual tensors to/from CPU/GPU, but dynamo's meta tensor tracking doesn't follow — resulting in a device mismatch.

**Fix:** Set `torch._dynamo.config.disable = True` at the **very top** of the server script, before any `torch` import that could trigger dynamo initialization:

```python
import torch
torch._dynamo.config.disable = True          # MUST be before other torch imports
torch._dynamo.config.suppress_errors = True  # optional safety net

from diffusers import DiffusionPipeline
# ... rest of imports
```

**Why env vars don't work:** `TORCH_COMPILE_DISABLE=1` and `PYTORCH_JIT=0` do NOT disable dynamo — they only control `torch.jit` and the older `torch.compile` API, not the new `_dynamo` module. The Python-side config flag is required.

**Why placement in `runscript.sh` doesn't work:** Setting `torch._dynamo.config.disable = True` inside a bash-wrapped Python subprocess that launches uvicorn may not propagate because the module initialization order is complex. **Place it at the top of the Python file that uvicorn loads**, not in a surrounding shell wrapper.

**Note:** `torch.backends.cudagraphs.enabled = False` is **not available** in PyTorch 2.11+cuda13.0 on this server — attempting to set it raises `AttributeError: module 'torch.backends' has no attribute 'cudagraphs'`. Remove any such calls.

**Additional fixes in qwen_image_server_v2.py:**
- `JSONResponse` must be imported from `fastapi.responses`, not from `fastapi` directly:
  ```python
  from fastapi import FastAPI
  from fastapi.responses import JSONResponse  # NOT: from fastapi import JSONResponse
  ```
- `@app.on_event("startup")` is deprecated in FastAPI 0.100+; use lifespan context managers instead, but the old form still works and is non-critical.

## API Endpoints
- `GET /` → `{"status":"ok"}`
- `GET /health` → `{"status":"ok"}` **(required by benchmark clients — must be explicitly registered)**
- `GET /info` → `{"model":"Qwen-Image-2512","offload":"sequential_cpu_offload","gpu_free_gb":31.8,"gpu_total_gb":33.7}`
- `POST /generate` → JSON with `{"image_base64":"...","format":"png"}`

### Request schema
```json
{
  "prompt": "string (required)",
  "negative_prompt": "string (default: empty)",
  "num_inference_steps": "int 1-200 (default: 50)",
  "true_cfg_scale": "float 1-20 (default: 4.0)",
  "height": "int 256-2048 (default: 1024)",
  "width": "int 256-2048 (default: 1024)",
  "seed": "int (optional, omit for random)"
}
```

## Benchmark Results (sequential CPU offload, dynamo disabled)

Measured via `curl -w "TIME: %{time_total}s"` from local machine to 70.88:8000.

| Steps | Resolution | Total Time | Per-step (after step 1) | Throughput |
|-------|-----------|------------|-------------------------|------------|
| 1     | 512×512   | 7s         | —                       | ~8.6 img/hr |
| 5     | 512×512   | 22s        | ~3.8s                   | ~13.6 img/hr |
| 10    | 512×512   | 52s        | ~5.0s                   | ~11.5 img/hr |
| 20    | 512×512   | 91s        | ~4.4s                   | ~7.9 img/hr (~0.66 img/min) |
| 50    | 512×512   | est. ~4-5min | ~4-5s                   | est. ~0.27 img/min |

**Key observations:**
- Step 1 is slower (~7s) due to GPU kernel JIT compilation overhead
- Steps 2+ are ~4-5s each with dynamo disabled
- At 1024×1024, even 10 steps times out (>600s) due to larger tensor sizes
- `sequential_cpu_offload()` is fundamentally slow for 57GB model — each step re-loads model from CPU

**Server was pre-warmed** — model already loaded when tests ran. Cold-start model loading takes ~60-90s.

## Performance Comparison: with vs. without dynamo fix

| State | 20-step/512×512 | Result |
|-------|-----------------|--------|
| Dynamo ENABLED (original server.py) | Crashes immediately with meta tensor error | ❌ |
| Dynamo DISABLED (fixed server_v2.py) | 91s, valid PNG returned | ✅ |

## Key Lessons from This Session
The user said "why do the rsync" after 60+ min transferring qwen_image_2512 from 70.88 → local → 70.92 when the model was already on 70.88 and the inference code could run there directly.

**Rule:** Before starting any model transfer, check if the destination server (where inference will run) already has the model. If yes, skip the transfer entirely.

### 2. rsync can exit 0 but silently fail to write files
Step 2 (local → 70.92) completed with `exit code 0` and `speedup is 1.00` but 0 bytes were written to the remote destination. The files were never on 70.92.

**Symptoms:**
- rsync exit 0 (success)
- No error about mkdir or write permission shown
- `du -sh` on remote shows 0 or wrong size
- `find /home/jianliu -name 'model_index.json'` returns nothing

**Root cause (discovered later):** The destination path `/data/models/` on 70.92 is owned by `rapidsdb`, and jianliu cannot write there. rsync's "mkdir failed: No such file or directory" error was actually a permission-denied-under-cover error — rsync couldn't create the destination directory because jianliu lacks write permission on `/data/`.

**Workaround:** Default to `/home/jianliu/` on target servers if `/data/` is locked. Always verify immediately:
```bash
ssh jianliu@TARGET "du -sh /destination/path/ && ls /destination/path/model_index.json"
```

### 3. Sequential CPU offload is extremely slow for diffusion models
`enable_sequential_cpu_offload()` means the GPU sits idle while model components are sequentially loaded from CPU RAM. For 512×512 @ 20 steps on 8× RTX 5090 with a 57GB model: ~91s (~4.5s/step). At 1024×1024, even 10 steps times out.

**Benchmark approach:** Test at low step counts (5-10 steps) first to gauge speed before running full benchmarks. Use `--max-time` on curl to avoid hanging.

### 4. PyTorch dynamo incompatibility is a real trap in PyTorch 2.x
The `torch.compile()` / dynamo system (enabled by default in PyTorch 2.x) is incompatible with `sequential_cpu_offload()`. Any diffusion pipeline using sequential CPU offload on PyTorch 2.x needs `torch._dynamo.config.disable = True` at the top of the script.

### 5. SSH from remote to remote fails if keys not distributed
70.88 → 70.92 SSH failed with `Permission denied (publickey,password)` because 70.92 didn't have 70.88's SSH pubkey. This forced the two-hop rsync via local machine.

## rsync Attempt → 70.92 (Failed, files never arrived)
- 70.88 `/data/models/qwen_image_2512/` → local: 57.7GB, exit 0, verified ✅
- local → 70.92 `/data/models/qwen_image_2512/`: exit 11, `mkdir failed: No such file or directory` ❌
- Cause: `/data/` on 70.92 owned by `rapidsdb`, jianliu cannot write there
- Fallback: local → 70.92 `/home/jianliu/qwen_image_2512/`: also exit 0 but 0 bytes transferred
- **Files never made it to 70.92** despite rsync exit 0
- `/data/` ownership on 70.92 is `rapidsdb:rapidsdb` — symlink creation also requires sudo

## Restart Sequence (Critical Pattern)

When restarting the server after a config change or crash:

```bash
# STEP 1: Kill old process (SSH session A)
ssh jianliu@10.10.70.88 "pkill -f qwen_image_server; sleep 1"

# STEP 2: Start new process (SSH session B — must be separate!)
ssh jianliu@10.10.70.88 "source ~/.bashrc && nohup /data/venvs/vllm-ds4/bin/python3 /tmp/qwen_image_server.py >/tmp/qwen_image_server.log 2>&1 &"

# STEP 3: Poll until server is ready (model loading takes ~30-60s)
ssh jianliu@10.10.70.88 "while ! curl -s http://localhost:8000/health 2>/dev/null | grep -q ok; do sleep 5; done; echo READY"
```

**Why separate SSH calls?** Chaining kill + start in one command (`ssh "pkill ...; nohup ... &"`) kills the newly spawned background process when the SSH session ends — the `&` only detaches from the shell, not from the SSH lifecycle.

**Why poll `/health`?** During model loading (~30-60s), the server returns 404 on all endpoints. Don't assume the server is up immediately after starting.

## Benchmark Timeout Issue

`qwen_benchmark.py` defaults: `--steps 20 --runs 3` at 512×512.

- Warmup: ~190s
- 3 runs: ~570s total
- **Total: ~760s — exceeds default 600s shell timeout**

For quick validation, use:
```bash
python qwen_benchmark.py --steps 10 --runs 1 --height 512 --width 512
```
This completes in ~150s (well under timeout).

## Adding the /health Endpoint (2026-06-08 fix)

The benchmark script checks `GET /health` first, falls back to `GET /` on connection error only. A 404 on `/health` is an HTTP error (not a connection error), so the fallback never triggers — the benchmark exits with "ERROR: cannot reach server".

Fix: add `/health` to the server script:
```python
@app.get("/health")
def health_check():
    return {"status": "ok"}
```

## /data/ Ownership — All Known Servers

| Server | `/data/` owner | jianliu writable? |
|--------|--------------|-------------------|
| 10.10.70.88 | `rapidsdb` | No — but model files already owned by `jianliu` within `/data/models/qwen_image_2512/` |
| 10.10.70.92 | `rapidsdb` | No — cannot write to `/data/` directly, must use `/home/jianliu/` |
| 10.10.70.95 | `rapidsdb` | No |
| 10.10.70.96 | `rapidsdb` | No |
| 10.10.70.98 | `rapidsdb` | No |