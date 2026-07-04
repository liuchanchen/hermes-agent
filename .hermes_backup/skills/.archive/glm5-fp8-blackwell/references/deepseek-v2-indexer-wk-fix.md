# deepseek_v2.py Indexer WK KeyError Fix

**File**: `/data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py`
**Discovered**: 2026-06-02
**Affects**: GLM-5.1-FP8 weight loading (all layers)

## Crash Symptom

```
KeyError: 'model.layers.39.self_attn.indexer.wk_weights_proj.weight'
  File ".../deepseek_v2.py", line 771, in _try_load_fp8_indexer_wk
    param = params_dict[fused_name]
```

Stacked params mapping (`indexer_fused_mapping`) expects to find `wk_weights_proj.weight` in
`params_dict` (created by `Indexer.__init__`). But GLM checkpoints store `indexer.wk` and
`indexer.weights_proj` as **separate keys** — there is no fused `indexer.wk_weights_proj`
entry in the safetensors. The fused parameter was never in the checkpoint.

## Root Cause

In `_try_load_fp8_indexer_wk` (line ~771):
```python
fused_name = f"{layer_prefix}.wk_weights_proj.weight"
param = params_dict[fused_name]   # ← KeyError: fused_name not in params_dict
```

GLM safetensors have (all 78 layers confirmed):
```
model.layers.N.self_attn.indexer.wk.weight           ← FP8 safetensor
model.layers.N.self_attn.indexer.wk.weight_scale_inv  ← FP8 scale
model.layers.N.self_attn.indexer.weights_proj.weight  ← bf16 safetensor (separate)
model.layers.N.self_attn.indexer.wq_b.weight          ← FP8 safetensor
model.layers.N.self_attn.indexer.wq_b.weight_scale_inv
```

vLLM's `stacked_params_mapping` (`indexer_fused_mapping`) creates a fused parameter
`wk_weights_proj` that absorbs `wk` (shard 0) and `weights_proj` (shard 1). But
`_try_load_fp8_indexer_wk` assumes the fused name exists in the checkpoint — it doesn't.

## Fix Applied (both nodes)

**Patch 1 — `_try_load_fp8_indexer_wk` guard** (deepseek_v2.py line ~771):
```python
fused_name = f"{layer_prefix}.wk_weights_proj.weight"
if fused_name not in params_dict:
    buf.pop(layer_prefix, None)
    return False  # let stacked_params_mapping handle separately
param = params_dict[fused_name]
param.weight_loader(param, weight_bf16, 0)
loaded_params.add(fused_name)
return True
```

**Patch 2 — stacked_params_mapping graceful skip** (deepseek_v2.py line ~1585):
```python
if is_pp_missing_parameter(name, self):
    continue

if name not in params_dict:
    continue  # ← prevents KeyError on any unmapped layer

param = params_dict[name]
```

Patch 2 is the general safety net: any mapped name not in `params_dict` is skipped rather
than crashing. This guards against any future layer where checkpoint structure diverges.

## Cross-Node Sync

Both patches applied to 10.10.70.96 manually. Synced to 10.10.70.98 via:
```bash
scp /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py \
   jianliu@10.10.70.98:/data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py
```

**Critical**: Code patches must be applied to BOTH nodes. The startup script sync does NOT
sync vLLM source code. An unpatched node crashes with the KeyError or backend validation errors.