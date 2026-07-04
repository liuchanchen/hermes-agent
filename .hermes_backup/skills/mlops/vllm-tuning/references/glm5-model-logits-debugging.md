# GLM-5.1-FP8 Model Logit Diagnostics

**Session**: 2026-06-02 | **Model**: GLM-5.1-FP8 @ 10.10.70.96/70.98 | **vLLM**: ds4-sm120

## Symptom

vLLM server generates deterministic but nonsensical output. Token logprobs ≈ -11.95
per token = log(154880), indicating near-uniform distribution over full vocabulary.

Example output:
```
" belleparticipants(Point方的UIButton被_emb libertsthrough..."
```

## Diagnostic Commands

### 1. Check model weight integrity

```python
# Run on 70.96 with vllm-ds4 venv activated
from safetensors import safe_open
import os, torch

model_dir = "/data/models/glm_5_1_fp8"

# Check lm_head
with safe_open(os.path.join(model_dir, "model-00001-of-00142.safetensors"), framework="pt") as f:
    t = f.get_tensor("lm_head.weight").float()
    print(f"lm_head: mean={t.mean():.6f}, std={t.std():.6f}, "
          f"near-zero={((t.abs()<1e-4).float().mean()*100):.1f}%")

# Check embed_tokens
with safe_open(os.path.join(model_dir, "model-00001-of-00142.safetensors"), framework="pt") as f:
    t = f.get_tensor("model.embed_tokens.weight").float()
    print(f"embed: mean={t.mean():.6f}, std={t.std():.6f}")
```

### 2. Count indexer weight keys

GLM has 553 indexer-related weight keys that MUST load:

```python
# Verify on 70.96
ssh jianliu@10.10.70.96 'source /data/venvs/vllm-ds4/bin/activate && python3 -c "
from safetensors import safe_open
import os

model_dir = \"/data/models/glm_5_1_fp8\"
indexer_keys = []
for fname in sorted(os.listdir(model_dir)):
    if not fname.endswith(\".safetensors\"):
        continue
    path = os.path.join(model_dir, fname)
    with safe_open(path, framework=\"pt\") as f:
        for k in f.keys():
            if \"indexer\" in k.lower():
                indexer_keys.append(k)

patterns = set()
for k in indexer_keys:
    p = k.replace(\"model.layers.\", \"\").split(\".\", 2)
    if len(p) >= 3:
        patterns.add(p[2])
print(f\"Total indexer keys: {len(indexer_keys)}\")
print(\"Unique patterns:\")
for p in sorted(patterns):
    print(f\"  layers.*.{p}\")
"
```

Expected output: 553 total keys, 7 unique patterns:
```
layers.*.indexer.k_norm.bias
layers.*.indexer.k_norm.weight
layers.*.indexer.weights_proj.weight
layers.*.indexer.wk.weight
layers.*.indexer.wk.weight_scale_inv     ← FP8, not bf16
layers.*.indexer.wq_b.weight
layers.*.indexer.wq_b.weight_scale_inv    ← FP8, not bf16
```

### 3. Inspect FP8 scale shapes

GLM uses 2D tile quantization (128×128 blocks), NOT per-channel:
- `q_a_proj.weight`: FP8 (2048, 6144), scale `(16, 48)` — 128×128 tile blocks
- `kv_a_proj_with_mqa.weight`: FP8 (576, 6144), scale `(5, 48)`
- `q_b_proj.weight`: FP8 (16384, 2048), scale `(128, 16)`
- MoE experts: scale shape varies by layer, dequantize with per-channel broadcast

### 4. API request with logprobs

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "glm5_1_fp8",
    "messages": [{"role": "user", "content": "say hello"}],
    "max_tokens": 5,
    "logprobs": 5
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
for i, lp in enumerate(d['choices'][0]['logprobs']['tokens']):
    print(f'token {i}: {lp}')
"
```

### 5. Check is_v32 value in loaded config

```bash
ssh jianliu@10.10.70.96 'source /data/venvs/vllm-ds4/bin/activate && python3 -c "
from transformers import AutoConfig
config = AutoConfig.from_pretrained(\"/data/models/glm_5_1_fp8\", trust_remote_code=True)
index_topk = getattr(config, \"index_topk\", 0)
is_v32 = index_topk > 0
print(f\"index_topk: {index_topk}\")
print(f\"is_v32: {is_v32}\")
print(f\"n_routed_experts: {config.n_routed_experts}\")
print(f\"num_experts_per_tok: {config.num_experts_per_tok}\")
print(f\"indexer_rope_interleave: {getattr(config, \'indexer_rope_interleave\', False)}\")
print(f\"num_nextn_predict_layers: {getattr(config, \'num_nextn_predict_layers\', 0)}\")
"
```

## Model Architecture Findings

| Parameter | Value |
|-----------|-------|
| vocab_size | 154,880 |
| hidden_size | 6,144 |
| num_hidden_layers | 78 |
| first_k_dense_replace | 3 |
| n_routed_experts | 256 |
| n_shared_experts | 1 |
| moe_intermediate_size | 2,048 |
| q_lora_rank | 2,048 |
| kv_lora_rank | 512 |
| rope_ratio | 1.0 |
| attention (use_mha) | False (uses MLA) |
| index_topk | **2,048** ← GLM IS a sparse MoE model |
| num_experts_per_tok | 8 (sigmoid scoring, top-8 of 256) |
| indexer_rope_interleave | true |
| num_nextn_predict_layers | 1 (MTP auxiliary layer at layer 78) |
| mlp_layer_types | dense (0–2), sparse/MoE (3–78) |

## Key Weight Structure

- **Dense layers (0–2)**: `gate_proj`, `up_proj`, `down_proj` (separate, NOT fused)
- **MoE layers (3–77)**: `gate_proj`, `up_proj`, `down_proj` per expert (0–255)
- **Shared experts** (all MoE layers): `shared_experts.gate_proj/up_proj/down_proj`
- **FP8 scales**: `*_weight_scale_inv` with 2D tile quantization shapes
- **Indexer** (all 78 layers + MTP layer 78): 553 keys total, both bf16 and FP8

## Root Cause: 553 Indexer Weights Skipped (RESOLVED 2026-06-02)

**Symptom**: Token logprobs ≈ -11.95 per token = log(154880), near-uniform distribution.

**Root cause**: When `is_v32=False` (forced by `--hf-overrides '{"index_topk": 0}'`), the
`DeepseekV2Attention.__init__` sets `self.indexer = None`. The weight loader then skips
ALL keys containing "indexer" (553 keys) via:

```python
if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name):
    continue  # 553 indexer keys skipped → random init → uniform logits
```

**Fix**: Patch `deepseek_v2.py` to always create the indexer module regardless of `is_v32`.
Apply on both 10.10.70.96 and 10.10.70.98. See `glm5-fp8-blackwell` SKILL.md §Required Patches #2.

## Open Questions

1. ~~Does GLM's separate-gate MLP structure correctly map to vLLM's weight stacking?~~ **RESOLVED: Yes, all weights load correctly. The indexer skip was the issue.**
2. Is the FP8 tile dequantization formula correct for GLM's quantization? **Unlikely the issue after indexer fix.**
3. Has this model ever produced correct output on any serving stack? **Unknown.** Official GLM serving tool should be tested if available.