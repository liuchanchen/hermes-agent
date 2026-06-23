# Blackwell SM 12.0 — vLLM Compatibility Matrix

## Venv Comparison

| Feature | `vllm-ds4` (ds4-sm120 branch) | `vllm-latest-cu130` (vLLM 0.22.0) |
|---------|-------------------------------|------------------------------------|
| Path | `/data/venvs/vllm-ds4/` | `/data/venvs/vllm-latest-cu130/` |
| vLLM | 0.6.0.dev0+cu132 | 0.22.0 |
| CUDA | 13.2 | 13.0 |
| transformers | 5.9.0 | 5.x |
| Blackwell MLP support | ✅ Works (TRITON MoE) | ❌ CUTLASS FP8 linear crashes |
| `--reasoning-parser glm45` | Available | Not compatible with GLM |
| `--hf-overrides` | Works with patched is_v32 | Same mechanism |

## What vLLM 0.22.0 Cannot Do on Blackwell

```
RuntimeError: cutlass_gemm_caller, /workspace/csrc/libtorch_stable/quantization/w8a8/cutlass/c3x/cutlass_gemm_caller.cuh:51, Invalid status
```

The `CutlassFp8BlockScaledMMKernel` is hardcoded in vLLM 0.22.0 for FP8 W8A8 block-scaled
linear layers. The `c3x` directory (for compute capability 10.x series) does not include
SM 12.0 kernels. There is no env var (`VLLM_USE_TRITON_FP8` or similar) to override this.

**Verdict**: vLLM 0.22.0 is not usable on Blackwell for FP8 block-quantized models.
Stick with the `ds4-sm120` custom branch.

## `--reasoning-parser glm45` GLM Incompatibility

GLM-5.1-FP8 does NOT have native DeepSeek-style thinking/reasoning. When
`--reasoning-parser glm45` or `--reasoning-parser deepseek_v4` is set:

- All generated content goes into `reasoning`/`reasoning_content` fields
- `content` field becomes `null`
- The model doesn't output `<thinking>...</thinking> response` tags

**Fix**: Do not use `--reasoning-parser` or `--tool-call-parser` for GLM models.
These flags are designed for DeepSeek V4 models only.

## Sparse MLA Backends (FlashInfer XQA) Require FP8 on Blackwell

The error `XQA MLA only supports fp8 operation on SM120/SM121 GPUs, got torch.bfloat16 and torch.bfloat16`
comes from **FlashInfer** (both dense `FLASHINFER_MLA` and sparse `FLASHINFER_MLA_SPARSE`),
NOT from TRITON_MLA. FlashInfer's XQA kernel requires FP8 for BOTH query activations
AND kv_cache on Blackwell. With `--kv-cache-dtype auto`, kv_cache is bf16 → XQA gets
bf16 input → crash.

**Root cause**: When `is_v32=True` (sparse mode, triggered by `--hf-overrides '{"index_topk": 0}'`
via `hasattr`), vLLM auto-selects `FLASHINFER_MLA_SPARSE`. FlashInfer then requires FP8 for
both activations and kv_cache, but `--kv-cache-dtype auto` gives bf16.

**Fix**: Remove `--hf-overrides` entirely. Without the override, the indexer patch handles
loading correctly and `is_v32` is determined by the native config value.

**TRITON_MLA** with `--kv-cache-dtype auto` (bf16) works correctly on Blackwell because
TRITON_MLA's decode kernel handles bf16 kv_cache without requiring FP8. The 100 KB shared
memory OOM that `--kv-cache-dtype fp8` causes is specific to the Triton MLA fp8 kernel path,
not the bf16 path.

## MoE Backend: TRITON Only

```python
# Auto-selected on Blackwell (from startup log):
Using TRITON Fp8 MoE backend out of potential backends: ['AITER', 'FLASHINFER_TRTLLM',
'FLASHINFER_CUTLASS', 'DEEPGEMM', 'TRITON', 'MARLIN', 'BATCHED_DEEPGEMM', 'BATCHED_TRITON', 'XPU']
```

Do NOT set `VLLM_USE_DEEP_GEMM=1` — DeepGEMM does not support SM 12.0.

## Triton MLA Shared Memory Workaround — `num_stages=1` (CRITICAL)

Blackwell SM 12.0 (RTX PRO 6000 96GB) has **99 KB** shared memory per block.
The Triton MLA decode kernel (`_fwd_grouped_kernel_stage1` in
`vllm/v1/attention/ops/triton_decode_attention.py`) requests **100 KB** with `num_stages=2`
(double-buffering). This is a **kernel-level hardware limit** — `--enforce-eager`
does NOT prevent it. The Triton kernel is JIT-compiled at first inference time, not at
CUDA graph capture.

**Confirmed working config**: `--kv-cache-dtype auto` (bf16 KV cache avoids the Triton MLA
fp8 kernel path) + `num_stages=1` in the kernel code.

Set `--block-size 64` to reduce per-block memory pressure alongside `auto`.

## The `num_stages=2` → `num_stages=1` Fix (2026-06-03)

Apply via Python patch to `/data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py`:
```python
content = open('triton_decode_attention.py').read()
content = content.replace('num_stages=2', 'num_stages=1')
open('triton_decode_attention.py', 'w').write(content)
```

After patching, **verify syntax** and **sync to worker**:
```bash
ssh jianliu@TARGET "python3 -m py_compile /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py && echo syntax OK"
# Then sync:
ssh jianliu@10.10.70.96 "base64 /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py" \
  | ssh jianliu@10.10.70.98 "base64 -d > /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py && python3 -m py_compile /data/vllm-ds4-sm120/vllm/v1/attention/ops/triton_decode_attention.py && echo synced"
```

After the code fix, restart vLLM — the Triton kernel will be JIT-compiled with `num_stages=1`
and pass Blackwell's 99 KB smem limit.

## Other Backend Support

| Feature | Blackwell (SM 12.0) |
|---------|---------------------|
| FlashInfer MLA | Partial (fp8 only, 8-query-head limit) |
| FlashMLA | Not compiled for SM 12.0 |
| FlashAttn MLA | Not compiled for SM 12.0 |
| CUTLASS (dense linear) | ❌ |
| CUTLASS (FP8 block-scaled) | ❌ |
| Triton (MLA attention) | ✅ (with shared-memory workaround) |
| Triton (MoE) | ✅ |
| FlashInfer (sampling) | ✅ |
