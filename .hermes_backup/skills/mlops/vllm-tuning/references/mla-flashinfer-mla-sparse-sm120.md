# FlashInfer MLASparse: "compute capability not supported" on SM 12.0

**Date:** 2026-06-03  
**Error class:** `ValueError: No valid attention backend found for cuda`  
**Confirmed in session:** squeeze-patch isolated to this as the terminal blocker after
  `_try_load_fp8_indexer_wk` and `is_v32` patches are applied.

## Error Transcript

```
ValueError: No valid attention backend found for cuda with
AttentionSelectorConfig(head_size=576, dtype=torch.bfloat16,
  kv_cache_dtype=fp8_e4m3, block_size=None, use_mla=True,
  has_sink=False, use_sparse=True, use_mm_prefix=False,
  use_per_head_quant_scales=False, attn_type=AttentionType.DECODER,
  use_non_causal=False, use_batch_invariant=False).
Reasons: {
  FLASHINFER_MLA:           [sparse not supported],
  CUTLASS_MLA:              [sparse not supported],
  FLASH_ATTN_MLA:           [kv_cache_dtype not supported,
                              sparse not supported,
                              compute capability not supported,
                              FlashAttention MLA not supported on this device],
  FLASHMLA:                [sparse not supported,
                              compute capability not supported,
                              vllm._flashmla_C is not available,
                              likely was not compiled due to insufficient nvcc
                              version or a supported arch was not in the list
                              of target arches to compile for.],
  TRITON_MLA:              [sparse not supported],
  FLASHINFER_MLA_SPARSE:    [compute capability not supported],
  FLASHMLA_SPARSE:          [kv_cache_dtype not supported]
}.
```

## Root Cause

FlashInfer's C++/CUDA kernels for `FLASHINFER_MLA_SPARSE` (XQA MLA sparse kernel) were
compiled **without** SM 12.0 (Blackwell) in `TORCH_CUDA_ARCH_LIST`.

vLLM's ds4-sm120 editable install at `/data/vllm-ds4-sm120/` was built with the default
arch list, which typically targets SM 8.x (A100), SM 9.0 (H100), and SM 10.0 (H200/Grace-Hopper).
SM 12.0 (Blackwell / RTX PRO 6000) was not included.

This is NOT a code-level Python patch. It is a **CUDA compilation arch list issue**.
Patching the Python files (the CC 12.0 capability guards, squeeze patch, etc.) can get
past code-level checks, but if FlashInfer was never compiled for SM 12.0, the kernel
will never load regardless.

## Fix

Rebuild vllm-ds4-sm120 with explicit CUDA arch list including Blackwell:

```bash
cd /data/vllm-ds4-sm120/
source /data/venvs/vllm-ds4/bin/activate

# Clean previous build artifacts (important — cached .so files are arch-specific)
pip install -e . --no-build-isolation 2>&1 | tail -20
```

But the real fix requires passing the arch list at build time. Since this is an
**editable install** (`pip install -e .`), the build is triggered by `pip install`.
The correct approach is:

```bash
# Option A: via environment variable during pip install
TORCH_CUDA_ARCH_LIST="9.0;12.0" pip install -e /data/vllm-ds4-sm120/ --no-build-isolation

# Option B: rebuild FlashInfer separately with SM 12.0
# (FlashInfer is a vllm dependency; if it's bundled/compiled as part of vllm build,
#  the env var approach above is sufficient)

# Option C: if using a pre-built FlashInfer wheel, replace it with one built for SM 12.0
pip uninstall flashinfer -y
# Reinstall from source with SM 12.0 support:
FLASHINFER_CUDA_ARCHS="9.0;12.0" pip install flashinfer --no-binary --no-build-isolation
```

After rebuild, verify:
```bash
source /data/venvs/vllm-ds4/bin/activate
python3 -c "
import vllm
# Check if _flashmla_C (FlashMLA native extension) is available
try:
    from vllm._flashmla_C import *
    print('FlashMLA extension: AVAILABLE')
except ImportError as e:
    print(f'FlashMLA extension: NOT AVAILABLE ({e})')
"
```

## Squeeze Patch Diagnostic Sequence

The terminal blocker was found by progressively removing code and observing where the
crash moved to:

| Squeeze location | Crash after squeeze | Interpretation |
|------------------|---------------------|----------------|
| None (baseline) | `ValueError: block_tables must be 2D` at `forward_mqa` | Original bug; patch needed |
| `squeeze(1) if ndim==3` | `load_model → make_layers → ... → attn_backend` | Patch worked; deeper blocker revealed |
| `hasattr(indexer, ...)` guard at top of `__init__` | Same `attn_backend` error | Not the blocker |
| Remove `self.mla_attn = MLAAttention(...)` call | `init_device` error | `__init__` itself is the real blocker |
| Remove `self.self_attn = attn_cls(...)` call | `init_device` error | `attn_cls` is the real blocker |
| Remove the entire `DeepseekV2Attention` body → bare `pass` | `init_device` error | Still blocked upstream |
| Patch `init_device` to return early | `load_model` error | Patch needed at model loading layer |
| Squeeze at `make_layers` | **"No valid attention backend"** | FINAL BLOCKER after all prior patches |

The squeeze path confirms: all code-level patches are correct and applied. The final
blocker is a **build-time/compilation issue** — FlashInfer's MLA sparse kernel was
compiled without SM 12.0 support.

## Key Diagnostic Patterns

1. **"compute capability not supported"** in a backend reason → that backend's CUDA
   kernel was never compiled for the target GPU arch. Fix: rebuild with correct
   `TORCH_CUDA_ARCH_LIST`.

2. **`vllm._flashmla_C is not available`** → the FlashMLA native extension was not
   compiled for this machine's CUDA architecture. Rebuild vllm from source with the
   correct arch list.

3. **`FLASHMLA` vs `FLASHINFER_MLA_SPARSE`**: Both MLASparse variants fail here.
   `FLASHMLA` (native FlashMLA extension) also fails with "compute capability not
   supported" and "likely was not compiled due to insufficient nvcc version or a
   supported arch was not in the list of target arches". `FLASHINFER_MLA_SPARSE`
   fails with just "compute capability not supported". Both are arch compilation issues.

4. **`TRITON_MLA` fails with "sparse not supported"** — this is a code-level
   validation rejection (sparse config vs. dense backend), NOT a compilation issue.
   If all other backends are blocked by compile issues, TRITON_MLA is also unavailable
   for sparse mode — but would work for dense mode (`is_v32=False`).