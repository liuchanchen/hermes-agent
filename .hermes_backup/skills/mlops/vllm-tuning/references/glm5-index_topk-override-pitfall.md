---
description: Root cause analysis of --hf-overrides index_topk crash on Blackwell
category: mlops/glm5-fp8-blackwell
tags: [glm, blackwell, vllm, sparse-backend, mla, troubleshooting]
---

# `index_topk` Override Pitfall — Root Cause Analysis

## The Crash

```
backendEnum.TRITON_MLA is not valid for this configuration. Reason: ['sparse not supported']
```

Worker crashed at startup. The `--hf-overrides '{"index_topk": 0}'` flag was present in the startup script.

## Actual Code

```python
# deepseek_v2.py
self.is_v32 = hasattr(config, "index_topk") and getattr(config, "index_topk", 0) > 0
```

With `--hf-overrides '{"index_topk": 0}'`:
- `hasattr(config, "index_topk")` → `True` (attribute exists, value 0)
- `getattr(config, "index_topk", 0) > 0` → `0 > 0` → `False`
- `is_v32 = True and False` → **`False`** ← so `use_sparse=False` in the attention config

BUT — in the backend candidate selector, the `is_v32=False` branch still includes
sparse backends (`FLASHMLA_SPARSE`, `FLASHINFER_MLA_SPARSE`) in the candidate list:

```python
# cuda.py — is_v32=False branch (simplified)
return [
    AttentionBackendEnum.FLASH_ATTN_MLA,
    AttentionBackendEnum.FLASHMLA,
    AttentionBackendEnum.FLASHINFER_MLA,
    AttentionBackendEnum.TRITON_MLA,
    AttentionBackendEnum.FLASHMLA_SPARSE,   # ← included even when is_v32=False!
]
```

## Why Sparse Backends Are Tried Even When `is_v32=False`

The dense branch includes sparse backends as fallback options. The sparse backend
validation then runs: `use_sparse != cls.is_sparse()` → `False != True` → rejected.

`FLASHINFER_MLA_SPARSE` uses the XQA MLA kernel which requires FP8 dtypes on SM120.
With `--kv-cache-dtype auto` (BF16 KV cache), the kernel crashes:

```
ValueError: XQA MLA only supports fp8 operation on SM120/SM121 GPUs,
got torch.bfloat16 and torch.bfloat16
```

The "sparse not supported" / "TRITON_MLA is not valid" error is misleading — it appears
when TRITON_MLA is tried AFTER the sparse backends fail. The real issue is that sparse
backends are in the candidate list at all when `index_topk` exists (even as `0`).

## Key Insight: `hasattr` vs `getattr`

```python
hasattr(config, "index_topk")    # True if attr EXISTS — checks attribute presence
getattr(config, "index_topk", 0)  # returns the VALUE (including 0 or None)

# With --hf-overrides '{"index_topk": 0}':
hasattr(config, "index_topk")    # True  ← attribute exists
getattr(config, "index_topk", 0) # 0     ← falsy but EXISTS
```

The code uses `hasattr` (existence check), not `getattr > 0` (value check). Any existing
`index_topk` — even `0` or `None` — causes `hasattr=True` → sparse backends included.

## With `index_topk` Absent from Config

```python
hasattr(config, "index_topk")    # False → is_v32=False
```

In the `is_v32=False` candidate list (on Blackwell), the sparse backends are REMOVED
from the list by an earlier condition check (before reaching cuda.py):

```python
# cuda.py — actual logic
if use_mla:
    if use_sparse:
        sparse_backends = [FLASHMLA_SPARSE, FLASHINFER_MLA_SPARSE]
        return [FLASHINFER_MLA, CUTLASS_MLA, FLASH_ATTN_MLA, FLASHMLA,
                TRITON_MLA, *sparse_backends]   # ← sparse only if use_sparse=True
    else:
        return [FLASHINFER_MLA, CUTLASS_MLA, FLASH_ATTN_MLA,
                FLASHMLA, TRITON_MLA]            # ← no sparse backends
```

So `use_sparse=False` → `is_v32=False` branch → no sparse backends → TRITON_MLA selected
cleanly → **no crash**.

## Fix Applied

1. **Remove `--hf-overrides '{"index_topk": 0}'`** from startup scripts on both nodes.
   After the always-create-indexer patch, indexer weights load correctly without any override.
2. **Verify both nodes** after patching the script:
   ```bash
   ssh 70.98 'grep hf-overrides /data/model_startup_script/start_glm5_fp8_2node.sh'
   ```
   The old processes may still be running the OLD script (with the override).

## If Sparse Backends Still Fail

If the model runs in native `is_v32=True` mode (sparse MoE) and sparse backends crash
on Blackwell, force the dense variant:
```bash
--attention-backend FLASHMLA
```