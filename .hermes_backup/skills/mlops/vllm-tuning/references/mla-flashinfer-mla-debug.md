# FlashInfer MLA block_tables Debug Notes (2026-06-03)

## Error

```
ValueError: block_tables must be 2D for shared paged KV layout, got ndim=3
  File "flashinfer_mla_sparse.py", line 351, in forward_mqa
    o = trtllm_batch_decode_with_kv_cache_mla(...)
  File "...flashinfer/mla/_core.py", line 707, in trtllm_batch_decode_with_kv_cache_mla
    return xqa_batch_decode_with_kv_cache_mla(...)
  File "...flashinfer/mla/_core.py", line 925, in xqa_batch_decode_with_kv_cache_mla
    kv_cache = _check_trtllm_gen_mla_shape(...)
  File "...flashinfer/utils.py", line 626, in _check_block_tables_shape
    raise ValueError(f"...got ndim={block_tables.ndim}")
```

## Shape Analysis

| Tensor | Shape | Notes |
|--------|-------|-------|
| `topk_indices_buffer` | `[max_num_batched_tokens, NUM_TOPK_TOKENS]` | Pre-allocated in `deepseek_v4.py` line 1266 |
| `topk_indices` (sliced) | `[num_actual_tokens, NUM_TOPK_TOKENS]` | 2D |
| `topk_indices_physical` (Triton output) | `[num_actual_tokens, NUM_TOPK_TOKENS]` | 2D — Triton kernel produces exactly this shape |
| `topk_indices_physical.unsqueeze(1)` | `[num_actual_tokens, 1, NUM_TOPK_TOKENS]` | 3D — WRONG, causes error |
| FlashInfer expects (`shared paged`) | `[batch, max_num_pages]` | 2D only |

The FlashInfer `xqa_batch_decode_with_kv_cache_mla` expects `block_tables` to be 2D
when `uses_shared_paged_kv_idx=True` (default). With `unsqueeze(1)`, ndim=3 triggers
the check failure.

## FlashInfer check code

```python
# flashinfer/utils.py:_check_block_tables_shape
expected_ndim = 2 if uses_shared_paged_kv_idx else 3
if block_tables.ndim != expected_ndim:
    raise ValueError(f"...got ndim={block_tables.ndim}")
```

## Why xpu_mla_sparse.py doesn't hit this

The xPU path in `xpu_mla_sparse.py` calls `_forward_bf16_kv` (not `trtllm_batch_decode_with_kv_cache_mla`).
It passes `topk_indices_global` directly without unsqueeze. Different kernel path.

## Fix

```python
# flashinfer_mla_sparse.py line 358
OLD: block_tables=topk_indices_physical.unsqueeze(1),
NEW: block_tables=topk_indices_physical.squeeze(1) if topk_indices_physical.ndim == 3 else topk_indices_physical,
```

Apply with: `python3 scripts/fix_flashinfer_mla_block_tables.py`

## Confounding Factor: Wrong venv

The startup script `/data/model_startup_script/start_glm5_fp8_2node.sh` was sourcing
`/data/venvs/vllm-latest-cu130/bin/activate` instead of `/data/venvs/vllm-ds4/bin/activate`.
v0.22.0 (vllm-latest-cu130) was running instead of 0.6.0.dev0+cu132 (vllm-ds4).

Direct invocation of vllm from the correct venv showed the right version. The startup
script showed 0.22.0 — proving the wrong venv was active.

Fix startup script:
```bash
# In /data/model_startup_script/start_glm5_fp8_2node.sh:
-source /data/venvs/vllm-latest-cu130/bin/activate
+source /data/venvs/vllm-ds4/bin/activate
```

## Verification steps

```bash
# 1. Verify version in startup script output
bash -c 'source /data/model_startup_script/start_glm5_fp8_2node.sh 2>&1 | head -3'
# Must show: 0.6.0.dev0+cu132

# 2. Apply patch
python3 scripts/fix_flashinfer_mla_block_tables.py

# 3. Kill stale processes
ssh jianliu@TARGET "pkill -9 -f 'vllm serve'"

# 4. Restart and monitor
ssh jianliu@TARGET "bash /data/model_startup_script/start_glm5_fp8_2node.sh master > /tmp/master_log.txt 2>&1 &"
```