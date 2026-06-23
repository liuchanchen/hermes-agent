# GLM-5.1-FP8 2-Node Deployment

**Model:** `GlmMoeDsaForCausalLM` (GLM-5.1, FP8 quantized)
**Architecture:** DeepSeek V2 style MLA, 256 routed experts, 8 experts/tok, 78 layers
**Config:** hidden_size=6144, kv_lora_rank=512, head_dim=64 (MLA head_size=576)
**Model size:** ~772B params, 704 GB FP8 checkpoint, 142 safetensors shards
**Quantization:** FP8 E4M3, weight_block_size=[128,128]
**Context limit:** max_position_embeddings=202752, deployed with max_model_len=65536

**Setup:** 70.96 (master) + 70.98 (worker), ConnectX-6 RoCE v2
**GPU:** 2 nodes x 8x RTX PRO 6000 Blackwell SE (96GB each) = 1.5 TB total
**vLLM:** 0.6.0.dev0 (jasl/vllm, ds4-sm120 branch from `/data/vllm-ds4-sm120/`)
**venv:** `/data/venvs/vllm-ds4/`
**Startup script:** `/data/venvs/vllm-ds4/start_glm5_fp8_2node.sh`

## Required Setup Steps

### 1. Transformers v5 Upgrade

The `glm_moe_dsa` model_type is NOT recognized by transformers v4. The model config specifies `transformers_version: 5.4.0`.

```bash
source /data/venvs/vllm-ds4/bin/activate
pip install --upgrade 'transformers>=5.4.0'
```

### 2. HuggingFace Hub Version Fix

If worker fails with `ImportError: cannot import name 'is_offline_mode' from 'huggingface_hub'`, upgrade:
```bash
pip install --upgrade huggingface_hub
```

### 3. Blackwell CC 12.0 Patches (Required)

The MLA attention backends in ds4-sm120 branch only support CC 9 (Hopper) and CC 10. RTX PRO 6000 Blackwell SE is CC 12.0. Patch these files on BOTH nodes:

Files to patch (all under `/data/vllm-ds4-sm120/vllm/`):
- `platforms/cuda.py` — change `major == 10` to `major in [10, 12]` (2 occurrences)
- `v1/attention/backends/mla/flashmla_sparse.py` — add 12 to capability list
- `v1/attention/backends/mla/flashinfer_mla_sparse.py` — add 12
- `v1/attention/backends/mla/flashinfer_mla.py` — add 12
- `v1/attention/backends/mla/cutlass_mla.py` — add 12
- `v1/attention/backends/mla/prefill/selector.py` — add 12
- `v1/attention/backends/mla/prefill/trtllm_ragged.py` — add 12
- `v1/attention/backends/mla/prefill/flashinfer.py` — add 12

Always clear `__pycache__` after patching:
```bash
find /data/vllm-ds4-sm120 -name '__pycache__' -path '*/vllm/*' -exec rm -rf {} + 2>/dev/null
```

### 4. Model Loading Fix: `wk_weights_proj` KeyError

In `vllm/model_executor/models/deepseek_v2.py` (~line 771), add a guard before `params_dict[fused_name]`:
```python
fused_name = f"{layer_prefix}.wk_weights_proj.weight"
if fused_name not in params_dict:
    return False  # fused param not available, let stacked_params_mapping handle it
param = params_dict[fused_name]
```

Without this, GLM weights fail with:
```
KeyError: 'model.layers.N.self_attn.indexer.wk_weights_proj.weight'
```

### 5. Sparse MLA Issue (index_topk)

The model has `index_topk: 2048` in config.json, forcing `use_sparse=True`. Neither sparse backend works on Blackwell:
- `FLASHINFER_MLA_SPARSE`: 3D HND page tables incompatible with FlashInfer's 2D expectation
- `FLASHMLA_SPARSE`: not compiled for CC 12.0

Workaround: patch `is_v32` check in deepseek_v2.py (lines 985, 1216):
```python
# Change from:
self.is_v32 = hasattr(config, "index_topk")
# To:
self.is_v32 = hasattr(config, "index_topk") and getattr(config, "index_topk", 0) > 0
```
Then pass `--hf-overrides '{"index_topk": 0}'` in the startup script.

## Performance Notes

- **Model loading:** 142 shards, ~704 GB, ~14 seconds on EXT4 (no prefetch)
- **Per-GPU memory after load:** 43.24 GiB (out of 96 GiB)
- **Torch compile first graph (1,8192):** ~17 seconds

### 6. Indexer Weight Loading (when is_v32=False)

When `index_topk` is overridden to 0, the model's indexer module is not created, but the checkpoint still contains indexer weights. Add a skip guard in `deepseek_v2.py` (~line 1535, before `_try_load_fp8_indexer_wk`):

```python
if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name):
    continue
```

Without this, the worker fails with:
```
AttributeError: 'GlmMoeDsaForCausalLM' object has no attribute 'indexer'
```

Note: `GlmMoeDsaForCausalLM` is a bare subclass (`class GlmMoeDsaForCausalLM(DeepseekV2ForCausalLM): pass`), so the indexer attribute is only set conditionally in the constructor when `is_v32` is True.

### 7. Attention Backend Auto-Selection

Even with `index_topk=0` and `use_sparse=False`, on Blackwell the auto-selector still picks `FLASHINFER_MLA_SPARSE` when `--kv-cache-dtype fp8` is set -- the priority list for CC 12.0 is:
1. `FLASHINFER_MLA` (dense) -- `kv_cache_dtype=fp8` not supported with MLA
2. `CUTLASS_MLA` -- doesn't support DECODER attention type
3. `FLASH_ATTN_MLA` -- only CC 9
4. `FLASHMLA` -- only CC 9,10
5. `TRITON_MLA` -- all CC, but has `is_sparse=False` while request has `use_sparse=False` (OK)
6. `FLASHINFER_MLA_SPARSE` -- selected for CC 12 with fp8 kv_cache
7. `FLASHMLA_SPARSE` -- only CC 9,10

This means `FLASHINFER_MLA_SPARSE` wins on CC 12.0 even without sparse attention. It then fails with:
```
ValueError: XQA MLA only supports 128 query heads (head_group_ratio=128), got 8 query heads
```
(GLM has 64 heads, TP=8 gives 8 heads per GPU)

**Workarounds to try:**
- Remove `--kv-cache-dtype fp8` (let it default to `auto`/bf16) -- then `FLASHINFER_MLA` is not selected as top choice for `auto` kv_cache, giving `TRITON_MLA` a chance
- Explicitly set `--attention-backend TRITON_MLA` -- but needs to not conflict with sparse
- Note: the HND (Hybrid N-D) layout produces 3D page tables that FlashInfer's TRT-LLM kernel rejects with `block_tables must be 2D for shared paged KV layout, got ndim=3`

## Known Pitfalls

### Zombie GPU Process Cleanup

After vLLM crashes, GPU memory stays allocated by orphaned `VLLM::Worker_PP*` and `VLLM::Worker` processes. These are NOT visible via `ps | grep vllm` (they use custom process names). Check with `fuser`:

```bash
fuser -v /dev/nvidia0  # shows all processes holding GPU 0
fuser -k /dev/nvidia*  # kills ALL processes holding any GPU
```

After killing, verify:
```bash
nvidia-smi --query-gpu=index,memory.free --format=csv,noheader
# Expected: ~97239 MiB free on each GPU
```

Without this cleanup, restart fails with:
```
ValueError: Free memory on device cuda:0 (40.5/94.97 GiB) on startup is less than desired GPU memory utilization (0.92, 87.37 GiB)
```

The same applies to the master node -- when a master-side worker (`VLLM::Worker_PP0_TP*`) holds memory, the restart also fails. Always clean BOTH nodes before restarting.

### Safetensors Corruption During Transfer

After `tar | nc`, verify ALL shards:
```bash
source /data/venvs/vllm-ds4/bin/activate
python3 -c "
import os, glob
from safetensors import safe_open
for f in sorted(glob.glob('/data/models/glm_5_1_fp8/model-*.safetensors')):
    try:
        with safe_open(f, 'pt') as s: pass
    except Exception as e:
        print(f'CORRUPT: {os.path.basename(f)}')
"
```
Re-transfer corrupt files via `scp`.

### Port 29505 Conflict

Kill zombie worker holding the port:
```bash
kill -9 $(ss -tlnp | grep 29505 | grep -oP 'pid=\K[0-9]+')
```
