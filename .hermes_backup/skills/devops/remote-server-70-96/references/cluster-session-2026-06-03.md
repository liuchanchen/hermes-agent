# 70.96/70.98 Cluster Session — 2026-06-03

## GLM-5.1-NVFP4 Download Status

| Metric | Value |
|--------|-------|
| Total shards | 49 |
| Shards complete (17:00 CST) | 23 |
| Total downloaded | 224 GB |
| Active lock files | model-00024 to 00031 |
| Speed | ~5-6 GB/5min |
| Remaining | ~26 shards (~240 GB) |

**Status:** Download was interrupted/auto-resumed. HF download process exited after 23 shards. Locks indicate partial download may have restarted. Kill and restart if no progress in 30 min.

**Script:** `/tmp/download_nvfp4.py` (PID 331566, running HF download)

## PP=2 Cluster Crash (GLM-5.1-FP8)

**Master (70.96):**
- v0.6.0.dev0+cu132 (ds4-sm120 branch)
- PID 329710, started 16:36:37 CST
- Config: TP=8, PP=2, FP8 kv-cache, TRITON_MLA, enforce_eager, max_len=65536
- Serving `glm5_1_fp8` on port 8000 ✅

**Worker (70.98):**
- v0.22.0 (vllm-latest-cu130) — version mismatch vs master v0.6.0
- Ranks 8-15 connected at 16:23 (7 min AFTER worker started at 16:16)
- Master wasn't up until 16:36 — worker was waiting for TCPStore for 13 min
- TCPStore heartbeat crashed at 17:02 (5 min later, ~45 min after worker connected)

**Root cause:** PP=2 requires worker to stay connected to master's TCPStore from startup through full model init. The 5-min heartbeat timeout kills the connection if master takes too long to load model weights + run KVCache profiling.

**Fix in progress:** Need to restart worker AFTER master is fully loaded.

## Two vLLM Instances on 70.98

- PID 621522: `vllm-ds4` (v0.22.0) — started via `start_glm5_fp8_2node.sh worker`
- PID 620441: `vllm-latest-cu130` (v0.22.0) — separate startup, no associated log

**GPU memory:** 80,332 MiB/card on 70.98 vs 74,764 MiB/card on 70.96
→ Extra ~5.5 GB/card × 8 = ~44 GB wasted on unnecessary second instance

## QwenImage-2512 on 70.88 (off-topic)

Model at `/data/models/qwen_image_2512/` is a **diffusion image generation pipeline** (QwenImagePipeline, 60-layer transformer), NOT a text LLM. vLLM cannot serve it. Server deployed with:

- Framework: `diffusers` + `FastAPI` + `uvicorn`
- venv: `/data/venvs/vllm-ds4`
- Memory strategy: `enable_sequential_cpu_offload()` (single GPU, ~1.8 GB during inference)
- Performance: 512×512 @ 20 steps ≈ 100s (single GPU), 1024×1024 ≈ 400s
- GPU utilization: 1 card only (sequential CPU offload moves one component at a time)
- Script: `/tmp/qwen_image_server.py` (PID 1080072)
- Endpoint: `http://10.10.70.88:8000`
- **Key insight:** `device_map="balanced"` (multi-GPU) is SLOWER than sequential CPU offload due to NCCL communication overhead on 8× RTX 5090 for this model architecture

## Notion Page Updated

https://www.notion.so/Qwen-Image-2512-5090-3744b7bb34d8804198a0e8b67122f843 — QwenImage-2512 deployment record with server script, API docs, performance benchmarks.