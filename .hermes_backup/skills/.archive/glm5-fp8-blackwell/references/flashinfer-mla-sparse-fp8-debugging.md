# FlashInfer MLA Sparse — XQA FP8 Crash Root Cause & Fix (2026-06-02)

## Error

```
ValueError: XQA MLA only supports fp8 operation on SM120/SM121 GPUs,
got torch.bfloat16 and torch.bfloat16
```

**Context**: GLM-5.1-FP8 with `is_v32=True` (native sparse mode, `index_topk=2048`),
running on Blackwell SM 12.0 (RTX PRO 6000 96GB). Startup script had
`--kv-cache-dtype auto`.

## Root Cause — Exact Code Path

### Stage 1: `is_quantized_kv_cache` gate

```
is_quantized_kv_cache("auto")
  → kv_cache_dtype.startswith("fp8")   # "auto".startswith("fp8")
  → False
```

**Key insight**: `"auto"` is a special string that means "detect from model config".
But `is_quantized_kv_cache()` only checks string prefixes — it doesn't look at the
resolved dtype. So `"auto"` always returns `False`, regardless of what the model
actually needs.

### Stage 2: fp8_attention flag

In `mla_attention.py` line 640:
```python
fp8_attention = is_quantized_kv_cache(self.kv_cache_dtype)
# With kv_cache_dtype="auto": fp8_attention = False
```

### Stage 3: Query tensor dtype decision (line 738)

```python
if fp8_attention and self.impl.supports_quant_query_input:
    assert mqa_ql_nope.shape[0] == mqa_q_pe.shape[0]
    assert mqa_ql_nope.shape[1] == mqa_q_pe.shape[1]
    mqa_q = self._decode_concat_quant_fp8_op(
        mqa_ql_nope, mqa_q_pe, self._q_scale
    )   # ← quantizes Q to float8_e4m3fn
else:
    mqa_q = (mqa_ql_nope, mqa_q_pe)    # ← Q stays bfloat16 ← THE BUG
```

With `fp8_attention=False` (from Stage 2), the `else` branch is taken.
`mqa_ql_nope` and `mqa_q_pe` remain bfloat16.

### Stage 4: XQA kernel assertion (FlashInfer)

In `flashinfer/mla/_core.py` `trtllm_batch_decode_with_kv_cache_mla`:
```python
assert query.dtype == torch.float8_e4m3fn, \
    f"XQA MLA only supports fp8 operation on SM120/SM121 GPUs, " \
    f"got {query.dtype} and {kv_cache.dtype}"
```

Both `query` and `kv_cache` are bfloat16 → assertion fires → `ValueError`.

## Why kv_cache itself is also bf16

With `--kv-cache-dtype auto`:
- `cache_config.cache_dtype = "auto"`
- In `torch_utils.py:kv_cache_dtype_str_to_dtype()`:
  ```python
  if kv_cache_dtype == "auto":
      return model_config.dtype if model_config else torch.half
  ```
- `model_config.dtype` is `bfloat16` → kv_cache allocated as bf16

## The Fix

Change in startup script:
```bash
# WRONG — causes XQA bfloat16 crash
--kv-cache-dtype auto

# CORRECT — enables FP8 throughout the sparse MLA path
--kv-cache-dtype fp8_e4m3
```

With `fp8_e4m3`:
1. `is_quantized_kv_cache("fp8_e4m3")` → `True`
2. `fp8_attention = True` → line 738 takes the `if` branch
3. `_decode_concat_quant_fp8_op` quantizes Q to `float8_e4m3fn`
4. kv_cache allocated as `uint8` (FP8 per `STR_DTYPE_TO_TORCH_DTYPE["fp8_e4m3"]`)
5. Both match → XQA kernel assertion passes

## Verification Steps

1. Check current flag value on both nodes:
   ```bash
   grep 'kv-cache-dtype' /data/model_startup_script/start_glm5_fp8_2node.sh
   ```

2. After fix, restart sequence:
   ```bash
   # User manually on 70.96 terminal:
   pkill -9 -f 'vllm serve'; sleep 2
   # User manually on 70.98 terminal:
   pkill -9 -f 'vllm'; sleep 1
   # Then start worker first, then master
   ```

3. Confirm FlashInfer sparse backend is used:
   ```
   vLLM engine started. Using FlashInfer MLA Sparse backend.
   ```

4. If crash persists after fix, the issue is a different backend selection —
   check the startup log for which backend is auto-selected.

## Related Code References

| File | Line | What it does |
|------|------|-------------|
| `vllm/utils/torch_utils.py:70` | `is_quantized_kv_cache()` | `"auto" → False` |
| `vllm/utils/torch_utils.py:287` | `_get_kv_cache_quant_algo_string()` | `"auto" → "fp8"` for FP8 checkpoints |
| `vllm/model_executor/layers/attention/mla_attention.py:640` | `fp8_attention = is_quantized_kv_cache(...)` | Gate for Q quantization |
| `vllm/model_executor/layers/attention/mla_attention.py:651` | `kv_cache = kv_cache.view(fp8_dtype())` | Cast kv_cache to FP8 |
| `vllm/model_executor/layers/attention/mla_attention.py:738` | Q tensor branch decision | The critical if/else split |
| `vllm/model_executor/layers/attention/mla_attention.py:490` | `_decode_concat_quant_fp8_op` | Q → FP8 quantization op |
| `flashinfer/mla/_core.py:102` | XQA assertion | The crash point |