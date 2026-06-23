# GLM-5.1-FP8 on 2-Node Blackwell (RTX PRO 6000, SM 12.0)

**Main reference**: `glm5-fp8-blackwell` skill (SKILL.md + references/) — the canonical, up-to-date
source. This file contains session-specific diagnostic detail.

## Model Info

- **Type**: GlmMoeDsaForCausalLM (maps to deepseek_v2 in vLLM ds4-sm120 branch)
- **Parameters**: ~772B (estimated), 256 routed experts, 8 experts/tok
- **Quantization**: FP8 (E4M3, weight_block_size 128x128)
- **Architecture**: DeepSeek V2-style MLA (kv_lora_rank=512, qk_rope_head_dim=64, head_size=576)
- **Context**: max_position_embeddings=202752 (practical: 65536)
- **Index topk**: 2048 (GLM IS a sparse MoE model — `is_v32=True` naturally)
- **MTP layer**: layer 78 has `num_nextn_predict_layers=1` auxiliary MTP layer

## Cluster

| Node | Role | IP (bond0) | GPUs |
|------|------|-----------|------|
| 70.96 | Master | 192.168.66.10 | 8x RTX PRO 6000 Blackwell (96GB) |
| 70.98 | Worker | 192.168.66.20 | 8x RTX PRO 6000 Blackwell (96GB) |

## Required Patches (vLLM ds4-sm120 branch)

Apply to `/data/vllm-ds4-sm120/` on **BOTH** nodes. After patching, clear all `__pycache__` dirs:
```bash
find /data/vllm-ds4-sm120 -name '__pycache__' -path '*/vllm/*' -exec rm -rf {} +
```

### 1. Blackwell CC 12.0 (8 files)
All MLA attention backends restrict compute capability to major 9 or 10. Add 12:
- `vllm/platforms/cuda.py`: `== 10` → `in [10, 12]` (2 occurrences)
- `vllm/v1/attention/backends/mla/flashmla_sparse.py`: `in [9, 10]` → `in [9, 10, 12]`
- `vllm/v1/attention/backends/mla/flashinfer_mla_sparse.py`: `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/flashinfer_mla.py`: `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/cutlass_mla.py`: `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/prefill/selector.py`: `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/prefill/trtllm_ragged.py`: `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/prefill/flashinfer.py`: `== 10` → `in [10, 12]`

### 2. is_v32 check (deepseek_v2.py, lines 985 and 1216)
```python
# ALREADY CORRECT in ds4-sm120 branch — no patch needed
self.is_v32 = hasattr(config, "index_topk") and getattr(config, "index_topk", 0) > 0
```

### 3. Always create indexer (deepseek_v2.py, ~line 988) — REQUIRED FIX

**This is the critical fix for garbled output.** Change the conditional indexer creation:

```python
# BEFORE — indexer None when is_v32=False → 553 indexer weights skipped → garbage logits
if self.is_v32:
    self.indexer = Indexer(...)
else:
    self.indexer_rope_emb = None
    self.indexer = None

# AFTER — indexer always created; sparse forward gated by topk_indices_buffer
self.indexer_rope_emb = get_rope(...)
self.indexer = Indexer(...)
```

Apply this patch on BOTH 10.10.70.96 and 10.10.70.98 after syncing the source file.

### 4. wk_weights_proj guard (~line 770)
```python
if fused_name not in params_dict:
    return False
param = params_dict[fused_name]
```

### 5. Skip indexer weights (~line 1547)
```python
# Already in ds4-sm120 — no additional patch needed
if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name):
    continue
```

## Indexer Weight Inventory

GLM checkpoint has **553 indexer-related weight keys** across all 78 layers + MTP layer 78:
```
model.layers.N.self_attn.indexer.k_norm.bias          (bf16)
model.layers.N.self_attn.indexer.k_norm.weight        (bf16)
model.layers.N.self_attn.indexer.weights_proj.weight  (bf16)
model.layers.N.self_attn.indexer.wk.weight            (bf16)
model.layers.N.self_attn.indexer.wk.weight_scale_inv  (FP8 e4m3)
model.layers.N.self_attn.indexer.wq_b.weight           (bf16)
model.layers.N.self_attn.indexer.wq_b.weight_scale_inv (FP8 e4m3)
```
All 553 keys must load. If skipped (when `indexer=None`), the indexer sub-module uses
random weights → near-uniform logit distribution → garbled output.

## Correct Startup Command (Updated 2026-06-02)

```bash
# Script: /data/model_startup_script/start_glm5_fp8_2node.sh (moved from venv dir)
# Worker (70.98) first:
ssh jianliu@10.10.70.98 "fuser -k /dev/nvidia*; bash /data/model_startup_script/start_glm5_fp8_2node.sh worker"
# Wait 15s, then master (70.96):
ssh jianliu@10.10.70.96 "fuser -k /dev/nvidia*; bash /data/model_startup_script/start_glm5_fp8_2node.sh master"
```

Key flags: TP=8, PP=2, EP=8, `--kv-cache-dtype auto` (NOT fp8), `--enforce-eager`,
`--hf-overrides '{"index_topk": 0}'` (forces `is_v32=False` → dense TRITON_MLA path),
no explicit `--attention-backend` (auto-selects correctly).

**Do NOT use `--attention-backend TRITON_MLA` with `is_v32=True`** — it causes
"sparse not supported" validation rejection.

## Error Summary (Updated 2026-06-02)

| Error | Root Cause | Fix |
|-------|-----------|-----|
| No valid attention backend (CC not supported) | All MLA backends cap at CC 10 | Patch 8 files to accept CC 12 |
| `block_tables must be 2D, got ndim=3` | FLASHINFER_MLA_SPARSE HND layout | Remove `--attention-backend TRITON_MLA` |
| `sparse not supported` | TRITON_MLA validates sparse mismatch | Use `--hf-overrides '{"index_topk": 0}'` or remove explicit backend |
| `OutOfResources: shared memory 102400 > 101376` | XQA kernel needs 100KB, Blackwell has 99KB | Use `--kv-cache-dtype auto` (avoids XQA path) |
| Garbled output (~log(vocab_size) logprobs) | 553 indexer weights skipped (indexer=None) | Always-create-indexer patch |
| `KeyError: wk_weights_proj.weight` | FP8 indexer fusion doesn't match GLM layout | Already handled by wk guard patch |
| `SafetensorError: incomplete metadata` | File corrupted during nc/tar transfer | Re-transfer the specific shard |

## Blackwell Shared Memory Limit — Key Finding

**Blackwell SM 12.0 (RTX PRO 6000) has 99 KB (101,376 bytes) shared memory per block.
Triton MLA kernels request 100 KB (102,400 bytes).**

Both `TRITON_MLA` decode kernel (`_fwd_grouped_kernel_stage1`) and
`FLASHINFER_MLA_SPARSE` XQA kernel trigger this OOM.

**`--enforce-eager` does NOT fix this** — the Triton MLA decode kernel is JIT-compiled
at first inference time (not CUDA graph capture time). Eager mode only skips CUDA graph
capture; the runtime kernel invocation still uses 100KB shared memory.

**Fix for garbled output**: The 553 indexer weight patch above.
**Fix for 100KB OOM**: `--kv-cache-dtype auto` avoids the Triton MLA decode path and uses
the dense MLA path instead, which uses a different (smaller-shared-memory) kernel.

**Note**: With `is_v32=True` (no `--hf-overrides`), the auto-selected
`FLASHINFER_MLA_SPARSE` backend crashes with the same 100KB error at inference time.
So `is_v32=False` + `--kv-cache-dtype auto` is currently the only working path.