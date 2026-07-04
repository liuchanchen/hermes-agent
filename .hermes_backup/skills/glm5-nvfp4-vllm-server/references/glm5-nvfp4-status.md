# GLM-5.1-NVFP4 on 70.96 — Configuration Snapshot (2026-06-08)

## Current Status

| Field | Value |
|-------|-------|
| **Status** | ✅ ACTIVE |
| **Checked** | 2026-06-08 |
| **Model** | `glm5_1_nvfp4` (NVIDIA, served as `glm5_1_fp8`) |
| **Served name** | `glm5_1_fp8` |
| **API server PID** | 30329 (root) |
| **Worker PIDs** | 31081–31088 (8× VLLM::Worker_TP*DCP*) |
| **Endpoint** | `http://10.10.70.96:8000/v1/models` |
| **GPU memory** | ~87,117 MiB/card (~89%) — all 8 GPUs idle |
| **GPU util** | 0% (no active requests) |
| **Log** | `/data/model_startup_script/glm5_nvfp4_docker.log` |

## Startup Method

Docker container via production script:
```
/data/model_startup_script/start_glm5_nvfp4_docker.sh
```

Script is self-contained (process cleanup → Triton cache clear → container start → vLLM exec → health poll).

## Docker Image

```
voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412
```

## vLLM Arguments

```bash
--model /data/models/glm_5_1_nvfp4/
--host 0.0.0.0 --port 8000
--served-model-name glm5_1_fp8
--trust-remote-code
--tensor-parallel-size 8
--decode-context-parallel-size 4
--gpu-memory-utilization 0.82
--max-num-seqs 64
--kv-cache-dtype bfloat16
--enable-prefix-caching
--enable-chunked-prefill
--tool-call-parser glm47
--chat-template-content-format=string
--enable-auto-tool-choice
--reasoning-parser glm45
--moe-backend b12x
```

## Health Check

```bash
# API alive?
curl -s --connect-timeout 5 http://localhost:8000/v1/models | grep glm5_1_fp8

# Engine alive? (always check this, not just API)
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
```

## Model Files

- Location: `/data/models/glm_5_1_nvfp4/`
- 49 shards (safetensors), ~434 GB total
- Download completed 2026-06-03 ~21:32 CST
- hf-mirror.com used (direct HF blocked by proxy)

## Restart Procedure

```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && sudo bash /data/model_startup_script/start_glm5_nvfp4_docker.sh"
```

Or step-by-step:
```bash
# 1. Kill
ssh jianliu@10.10.70.96 "pkill -9 -f 'vllm.*glm5_1_nvfp4'; sudo docker kill glm5_nvfp4_vllm 2>/dev/null; sleep 3"
# 2. Clear Triton cache
ssh jianliu@10.10.70.96 "rm -rf /root/.triton/cache"
# 3. Verify GPU free
ssh jianliu@10.10.70.96 "nvidia-smi --query-gpu=memory.used --format=csv,noheader"
# 4. Restart
ssh jianliu@10.10.70.96 "source ~/.bashrc && sudo bash /data/model_startup_script/start_glm5_nvfp4_docker.sh"
```

## History

| Date | Event |
|------|-------|
| 2026-06-03 ~21:32 | Model download completed |
| 2026-06-04 | Engine deadlock (PID 381662, Gloo/NCCL Connection closed by peer) |
| 2026-06-08 | Restarted via production script, now healthy |