# GLM-5.1-NVFP4 — Model Config & Deployment Notes

## Model Identity

| Field | Value |
|-------|-------|
| **Repo** | `nvidia/GLM-5.1-NVFP4` |
| **Local path** | `/data/models/glm_5_1_nvfp4/` |
| **Total size** | 434 GB (49×safetensors + config/tokenizer) |
| **Architecture** | `GlmMoeDsaForCausalLM` |
| **Layers** | 78 |
| **Experts** | 256 (sparse MoE, `topk_method=noaux_tc`) |
| **Experts/tok** | 8 (`num_experts_per_tok`) |
| **Hidden size** | 6144 |
| **Heads** | 64 attention, 64 KV (`num_key_value_heads`) |
| **Context** | 202,752 (`max_position_embeddings`) |
| **Vocab** | 154,880 |
| **Quantization** | NVFP4 (modelopt, 4-bit weights, 8-bit KV cache) |
| **Producer** | modelopt 0.45.0.dev44 |

## quantize_config.json (from model)

```json
{
  "quant_algo": "NVFP4",
  "kv_cache_scheme": {"dynamic": false, "num_bits": 8, "type": "float"},
  "producer": {"name": "modelopt", "version": "0.45.0.dev44+gc273ddb8a.d20260509"},
  "config_groups": {
    "group_0": {
      "input_activations": {"num_bits": 4, "type": "float", "group_size": 16, "dynamic": false},
      "weights": {"num_bits": 4, "type": "float", "group_size": 16, "dynamic": false}
    }
  },
  "ignore": ["lm_head", "model.layers.0*", ..., "model.layers.78*"]
}
```

Key: **KV cache uses fp8 (not NVFP4)** — set `--kv-cache-dtype fp8` in vLLM.
Ignored layers: first 3 dense layers + all attention layers (float/bfloat16 for those parts).

## Parallelism Strategy (TP=1 + DP=8 + EP)

Same strategy as `minimax_m2_nvfp4_70.96.sh` — verified working for MoE with Expert Parallel.

```
TP=1  → non-expert weights fit in one GPU (~3 GB for hidden_size=6144, 78 layers)
DP=8  → non-expert weights replicated across all 8 GPUs
EP    → 256 experts distributed: 256 / 8 = 32 experts per GPU
```

No NCCL multi-node communication needed (single node only).

## vLLM Serve Arguments

```bash
vllm serve /data/models/glm_5_1_nvfp4 \
  --host 0.0.0.0 --port 8000 \
  --trust-remote-code \
  --tensor-parallel-size 1 \
  --data-parallel-size 8 \
  --enable-expert-parallel \
  --gpu-memory-utilization 0.92 \
  --max-model-len 65536 \
  --kv-cache-dtype fp8 \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  --enable-auto-tool-choice \
  --served-model-name glm5_1_nvfp4 \
  --compilation-config '{"mode":3}'
```

## Docker Container Access

Image: `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412`
Running container: `ecstatic_shaw` (2026-06-03, up since 19:40 CST)

```bash
# jianliu is NOT in docker group. Use sudo with password:
ssh jianliu@10.10.70.96 "echo '!QAZ2wsx' | sudo -S docker exec ecstatic_shaw bash -c '...'"

# Inside container, venv is /opt/venv (vllm-ds4 is also at /data/venvs/vllm-ds4/)
# Container already has CUDA 13.0, NCCL 2.28.3, NVIDIA DRIVER 595.58.03
```

## Startup Script

**Script:** `/data/model_startup_script/start_glm5_nvfp4.sh`
**Venv:** `/data/venvs/vllm-ds4/` (not the container's `/opt/venv`)
**Log:** `/data/model_startup_script/glm5_nvfp4.log`

```bash
# Run from container or host (uses setsid internally if background):
bash /data/model_startup_script/start_glm5_nvfp4.sh
```