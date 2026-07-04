# Blackwell MLA Backend Patches for vLLM ds4-sm120 Branch

## When to Use

You're deploying a model with **Multi-head Latent Attention (MLA)** — DeepSeek V2/V3/V4, GLM-5.1-FP8, Kimi K2, etc. — on **Blackwell GPUs** (RTX PRO 6000, compute capability 12.0). vLLM engine fails with "No valid attention backend found" because all MLA backends restrict compute capability to Hopper (CC 9) or Blackwell v1 (CC 10).

## Affected GPUs

- NVIDIA RTX PRO 6000 Blackwell Server Edition (sm120, CC 12.0)
- Any future Blackwell-generation GPU (CC 12.x)

## Error Signature

```
ValueError: No valid attention backend found for cuda with AttentionSelectorConfig(
  head_size=576, dtype=torch.bfloat16, kv_cache_dtype=fp8, block_size=256,
  use_mla=True, has_sink=False, use_sparse=True, ...
). Reasons: {
  FLASH_ATTN_MLA: [compute capability not supported, ...],
  FLASHMLA: [compute capability not supported, ...],
  FLASHINFER_MLA: [compute capability not supported, ...],
  TRITON_MLA: [sparse not supported],
  FLASHMLA_SPARSE: [compute capability not supported]
}
```

## Patches Required

All paths are relative to the vLLM source tree (editable install directory).

### 1. Backend Priority Selector — `platforms/cuda.py`

Two places need changing:

```python
# Line ~87: MLA backend priorities for sparse-capable GPUs
if device_capability.major in [10, 12]:  # was: == 10

# Line ~128: Non-MLA backend priorities
if device_capability.major in [10, 12]:  # was: == 10
```

### 2. Sparse MLA Backends (4 files)

```python
# attention/backends/mla/flashmla_sparse.py
return capability.major in [9, 10, 12]  # was: [9, 10]

# attention/backends/mla/flashinfer_mla_sparse.py
return capability.major in [10, 12]      # was: == 10

# attention/backends/mla/flashinfer_mla.py
return capability.major in [10, 12]      # was: == 10

# attention/backends/mla/cutlass_mla.py
return capability.major in [10, 12]      # was: == 10
```

### 3. Prefill Backend Selectors (3 files)

```python
# attention/backends/mla/prefill/selector.py
if device_capability.major in [10, 12]:  # Blackwell  # was: == 10

# attention/backends/mla/prefill/trtllm_ragged.py
return device_capability.major in [10, 12]  # was: == 10

# attention/backends/mla/prefill/flashinfer.py
return device_capability.major in [10, 12]  # was: == 10
```

## Critical: Clear Python Cache After Patching

After editing .py files, the `__pycache__/` directories contain stale bytecode. vLLM subprocess workers load the cached bytecode, NOT the patched source files. This makes the patches appear to have no effect.

```bash
# Clear ALL vLLM bytecode caches on each node:
find /path/to/vllm-source -name '__pycache__' -path '*/vllm/*' -exec rm -rf {} +
```

## Verification

After patching and clearing cache, restart vLLM. The log should show a successful backend selection:

```
(Worker_PP0_TP0_EP0 pid=XXX) Using HND KV cache layout for FLASHINFER_MLA_SPARSE backend.
```

## Important Caveat

These patches only fix the **compute capability guard** — they allow the backend to be selected. The actual CUDA kernels may still not work correctly on Blackwell if the backend library (flashmla, flash-attn, etc.) hasn't been compiled for sm120. The first attention operation may produce wrong results or crash with CUDA errors.

This is a "make it try" patch, not a "make it work correctly" patch. The kernels must also support Blackwell.

## Known Second Blocker: FlashInfer TRT-LLM + HND KV Layout on Blackwell

After the CC 12.0 patches pass attention backend selection and weight loading completes, **CUDAGraph warmup** (`profile_cudagraph_memory` → `_dummy_run`) may fail with:

```
ValueError: block_tables must be 2D for shared paged KV layout, got ndim=3
```

**Root cause**: The `FLASHINFER_MLA_SPARSE` backend uses HND (Hybrid N-D) KV cache layout which produces 3D page tables, but the FlashInfer TRT-LLM MLA kernel (`trtllm_batch_decode_with_kv_cache_mla`) expects 2D page tables. This is a FlashInfer version incompatibility with the specific vLLM branch's KV cache memory management.

**Affects**: `FLASHINFER_MLA_SPARSE` backend — tested with block_size=256 and block_size=64.

**Possible mitigations** (not all verified):
1. Switch to `FLASHMLA_SPARSE` backend via `--attention-backend FLASHMLA_SPARSE` — uses a different KV cache layout that may be 2D-compatible
2. Try different block_size values (64, 128, 256) — the HND layout's ndim may change
3. Disable sparse attention entirely by removing `index_topk` from the model config (this would fall back to Triton MLA which is CC-agnostic)
4. Use a different attention backend patch path (e.g., make TritonMLA accept sparse mode)

Note: Model weight loading and attention backend selection both succeed — this error only appears during the CUDA graph capture phase.
