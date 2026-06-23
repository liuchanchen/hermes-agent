---
name: mla-blackwell
description: MLA (Multi-Head Latent Attention) deployment on Blackwell (SM 12.0) — GLM-5.1-FP8, DeepSeek-V4-Pro, and related models using vLLM ds4-sm120 branch with FlashInfer sparse backend.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# MLA on Blackwell — Deployment & Debugging

Deploying models with MLA attention on NVIDIA Blackwell (SM 12.0) GPUs using the `jasl/vllm ds4-sm120` branch. Covers GLM-5.1-FP8, DeepSeek-V4-Pro, and other MLA-based models.

## Models This Skill Covers

| Model | Architecture | Size | vLLM Backend |
|-------|-------------|------|---------------|
| GLM-5.1-FP8 | GlmMoeDsaForCausalLM | 704 GB FP8 | ds4-sm120 (FlashInfer MLA sparse) |
| DeepSeek-V4-Pro | DeepseekV4ForCausalLM | ~806 GB FP8 | ds4-sm120 (Triton MLA, no FlashInfer) |

Both use the ds4-sm120 branch at `/data/vllm-ds4-sm120/` with the editable venv at `/data/venvs/vllm-ds4/`.

## vLLM Setup

```
Source:     /data/vllm-ds4-sm120/         (jasl/vllm ds4-sm120 branch, editable install)
Venv:       /data/venvs/vllm-ds4/         (Python 3.12, PyTorch 2.11.0+cu130)
Version:    0.6.0.dev0+cu132
FlashInfer: 0.6.8.post1 (in vllm-ds4 venv)
Attention:  FLASHINFER_MLA_SPARSE backend (triton_convert_req_index_to_global_index + trtllm_batch_decode_with_kv_cache_mla)
```

Verify with:
```bash
source /data/venvs/vllm-ds4/bin/activate && vllm --version  # expect 0.6.0.dev0+cu132
python3 -c 'import vllm; print(vllm.__file__)'  # expect /data/vllm-ds4-sm120/vllm/__init__.py
```

## Startup Scripts

```
GLM-5.1-FP8 (2-node PP=2):  /data/model_startup_script/start_glm5_fp8_2node.sh
DeepSeek-V4-Pro (2-node PP=2): /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh
```

## Critical: Verify Correct venv Before Starting

The GLM-5.1-FP8 startup script has been seen with the **wrong venv sourced**. Always verify:

```bash
# Check what version the startup script will actually run
bash -c 'source /data/model_startup_script/start_glm5_fp8_2node.sh 2>&1 | head -3'
# Expected: 0.6.0.dev0+cu132 (not 0.22.0!)

# Also verify the venv path in the script itself
grep -n 'source.*activate' /data/model_startup_script/start_glm5_fp8_2node.sh
# CORRECT: source /data/venvs/vllm-ds4/bin/activate
# WRONG:   source /data/venvs/vllm-latest-cu130/bin/activate
```

v0.22.0 from vllm-latest-cu130 does NOT use the ds4-sm120 source (its editable points to a pip-installed vllm, not the git source). Any patches to `/data/vllm-ds4-sm120/vllm/` will have zero effect if the wrong venv is active.

## Known Issues & Fixes

### FlashInfer MLA block_tables shape mismatch (CRITICAL)

**Symptom:**
```
ValueError: block_tables must be 2D for shared paged KV layout, got ndim=3
  File "...flashinfer_mla_sparse.py", line 351, in forward_mqa
    o = trtllm_batch_decode_with_kv_cache_mla(...)
  File "...flashinfer/mla/_core.py", line 925, in xqa_batch_decode_with_kv_cache_mla
    kv_cache = _check_trtllm_gen_mla_shape(...)
  File "...flashinfer/utils.py", line 626, in _check_block_tables_shape
    raise ValueError(f"block_tables must be 2D for shared paged KV layout, got ndim={block_tables.ndim}")
```

**Root cause:** In `flashinfer_mla_sparse.py` line 358, `topk_indices_physical.unsqueeze(1)` transforms a 2D tensor `[num_tokens, NUM_TOPK_TOKENS]` into 3D `[num_tokens, 1, NUM_TOPK_TOKENS]`. FlashInfer 0.6.8.post1's `xqa_batch_decode_with_kv_cache_mla` expects exactly 2D for shared paged KV layout.

**Why it happens:** The `triton_convert_req_index_to_global_index` Triton kernel correctly outputs 2D. Then the code unnecessarily unsqueezes it for the batch dimension — but FlashInfer's `trtllm_batch_decode_with_kv_cache_mla` already expects `[batch, kv_index]` shape where `batch=1` is handled internally, not via an extra dimension.

**Fix (apply to `/data/vllm-ds4-sm120/vllm/v1/attention/backends/mla/flashinfer_mla_sparse.py`):**

```python
# Line 358 — BEFORE:
block_tables=topk_indices_physical.unsqueeze(1),

# AFTER:
block_tables=topk_indices_physical.squeeze(1) if topk_indices_physical.ndim == 3 else topk_indices_physical,
```

The `squeeze(1) if ndim==3 else` pattern is safe for both pre-fix (3D) and post-fix (2D) states.

**Apply the patch via:**
```bash
python3 scripts/fix_flashinfer_mla_block_tables.py
```

See `scripts/fix_flashinfer_mla_block_tables.py`.

**Reference:** `xpu_mla_sparse.py` handles the same `triton_convert_req_index_to_global_index` output without any unsqueeze — it passes `topk_indices_global` directly to `_forward_bf16_kv`. The xPU path doesn't use FlashInfer's `trtllm_batch_decode_with_kv_cache_mla`, which is why it doesn't hit this shape check.

### Triton MLA Shared Memory OOF on Blackwell (SM 12.0)

When using `--attention-config.backend=TRITON_MLA`, the Triton MLA decode kernel may
crash with:

```
triton.runtime.errors.OutOfResource: out of resource: shared memory,
Required: 102400, Hardware limit: 101376
```

**Root cause:** Blackwell SM 12.0 hardware limit is **99 KB (101,376 bytes)** per thread block.
The Triton MLA decode kernel uses `num_stages=2` (software pipelining), doubling shared memory
requirement to ~100 KB — exceeds the 99 KB Blackwell limit.

**Fix in `/data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py`:**
Change all `num_stages=2` → `num_stages=1`:

```python
# BEFORE (2 pipeline stages → 100KB → exceeds Blackwell 99KB limit):
num_stages = 2

# AFTER (1 pipeline stage → ~50KB → fits in 99KB Blackwell limit):
num_stages = 1
```

This requires `--enforce-eager` in the startup script (cudagraphs prevent patched kernels
from reloading with different `num_stages`).

Sync to worker:
```bash
base64 /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py \
  | ssh jianliu@10.10.70.98 "base64 -d > /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py \
    && python3 -c \"import py_compile; py_compile.compile('/data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py')\" \
    && echo synced"
```

## Debugging Workflow

When the server fails to start or crashes during first inference on MLA models:

**Step 1: Verify vLLM version**
```bash
ssh jianliu@TARGET "source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate && vllm --version"
# Must show 0.6.0.dev0+cu132
```

**Step 2: Check log for the specific error**
```bash
ssh jianliu@TARGET "tail -100 /tmp/vllm*.log | grep -E 'ERROR|ValueError|FlashInfer|block_tables'"
```

**Step 3: If block_tables error — apply the patch**
```bash
python3 scripts/fix_flashinfer_mla_block_tables.py
```

**Step 4: Force dense MLA if sparse backend selected**

> **Critical**: Even after model-class `is_v32=False` patches, vLLM's backend selector
> auto-selects `FLASHMLA_SPARSE` when `index_topk` is present in the HuggingFace config.
> The backend reads `index_topk` directly (`flashmla_sparse.py` line 316), bypassing the
> model-class flag. On SM 12.0 (Blackwell), `FLASHMLA_SPARSE` crashes with
> `ValueError: block_tables must be 2D` because FlashInfer's pre-built pip has a shape mismatch.

Force dense MLA by adding to the startup script:
```bash
--attention-config.backend=TRITON_MLA
```

> **Correct flag format**: `--attention-config.backend=TRITON_MLA` (via `AttentionConfig.backend`
> field in `vllm/config/attention.py`). The format `--attention-backend FLASHMLA` is **not valid**
> vLLM syntax.

**Step 5: Kill stale processes and restart**
```bash
ssh jianliu@TARGET "pkill -9 -f 'vllm serve'; sleep 3; ps aux | grep '[v]llm' | grep -v grep"
```

**Step 6: Check startup log**
```bash
ssh jianliu@TARGET "tail -f /tmp/vllm_glm5_master.log"
```

### Squeeze Patch Diagnostic Pattern

When the error is deep in vLLM internals (multiproc executor, model loading), use binary
search via Python patch to isolate which code change actually matters vs. which is a
consequence of a deeper blocker:

1. Identify the crash location in the traceback (e.g. `make_layers`, `__init__`, etc.)
2. Add a minimal no-op patch at that location (e.g. return early, skip the failing call)
3. Restart and check if the crash moves past that point
4. If it does → the patch was necessary but insufficient; the real error is the *next* one
5. Iterate until the traceback fully resolves

**This session's squeeze path**: squeeze at `MultiHeadLatentAttention.__init__` (line 377)
→ crash moved from `load_model` to `init_device` → squeeze at `init_device` → crash moved
from `init_device` to `__init__` → squeeze at `__init__` → **final blocker: no valid
attention backend** (FlashInfer not compiled for SM 12.0)

## PP=2 Startup Order

1. Worker first, wait ~45s
2. Master second
3. Verify: `curl http://localhost:8000/health`

## References

Detailed error transcripts and reproduction steps in `references/`:
See `references/flashinfer-mla-debug.md` — Full traceback analysis, shape investigation, and fix details
- `references/glm5-fp8-debug-2026-06-03.md` — Session notes from the session where this bug was found
- `references/flashinfer-mla-sparse-sm120.md` — FlashInfer MLASparse "compute capability not supported" on SM 12.0: root cause and rebuild fix