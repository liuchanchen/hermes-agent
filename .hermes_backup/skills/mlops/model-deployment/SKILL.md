---
name: model-deployment
description: ML model deployment workflows — multi-node vLLM server setup, DeepSeek-V4 configuration, tensor parallelism constraints, memory analysis, and distributed inference cluster management.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Model Deployment

Umbrella skill for deploying ML models to production inference servers. Covers multi-node vLLM setup, model-specific configuration constraints (FP8 block quantization, tensor parallelism sizing), memory analysis, and distributed serving cluster management.

## DeepSeek-V4 Multi-Node Deployment

Reference: `references/deepseek-v4-multi-node.md` for detailed DeepSeek-V4-Pro setup across 4 GPU servers.  **Startup scripts** copied to 70.88 benchmark dir: `/home/jianliu/work/bench_test/deepseekv4_pro/` (3 scripts: PP=2+EP, TP8+DP2+EP, DP16+EP). Scripts originally from 70.98's `/data/venvs/vllm-ds4/`.

### Standardized Benchmark Dirs on 70.88

All model benchmark infrastructure lives under `/home/jianliu/work/bench_test/`:

| Dir | Model | Scripts |
|-----|-------|---------|
| `deepseekv4_flash/` | DeepSeek V4 Flash | `start_dsv4_flash_1node.sh`, `test_deepseekv4_throughput_cache.py`, `run_benchmark.sh` |
| `qwen_3_6/` | Qwen3.6-35B-A3B-FP8 | `start_qwen36.sh` (DP=8), `start_qwen36_1node.sh` (TP8+EP) |
| `deepseekv4_pro/` | DeepSeek V4 Pro | `start_dsv4_pro_2node.sh`, `start_dsv4_pro_tp8_dp2_ep.sh`, `start_dsv4_pro_dp16_ep.sh` |
| `glm5_nvfp4/` | GLM-5.1-NVFP4 | `start_glm5_nvfp4_docker.sh` (Docker, from 70.96) |
| `minimax_m2_7/` | MiniMax M2.7-NVFP4 | `start_minimax_m2_nvfp4_tpep.sh` (copied from 70.95) |
| `vllm_bench_standard_test/` | Generic benchmark | `run_vllm_bench_serve.sh`, `test_vllm_bench_serve.py` — supports `--header` for auth-enabled servers (patched 2026-06-11) |
Reference: `references/multi-node-dp-diagnostics.md` for diagnosing multi-node Data Parallel clusters (70.96+70.98).
Reference: `references/qwen-image-2512-diffusion-server.md` — Qwen-Image-2512 diffusion pipeline deployment on 70.88. **Critical distinction: vLLM cannot serve diffusion models.** Correct stack is `diffusers + FastAPI + uvicorn`. Includes GPU offloading strategy comparison, measured generation times, torch.compile compatibility fix (`torch._dynamo.config.disable = True`), and benchmark results (0.31 img/min @ 512×512/20 steps).
- `scripts/qwen_benchmark.py` — reusable benchmark client for Qwen-Image-2512 servers (warmup + N runs, CLI args for resolution/steps/runs/url). See also local copy at `/home/jianliu/qwen_benchmark.py`.
Reference: `references/wan22-t2v-local-model.md` — Wan 2.2 T2V (`wan2.2_t2v_A14B`) local-format model on 70.88. Model is NOT in diffusers format — has separate MoE expert safetensors (`high_noise_model/`, `low_noise_model/`), T5 encoder `.pth`, and VAE `.pth`. The `.pth` files use a 5-tuple persistent ID format **incompatible with PyTorch 2.11+** (`_rebuild_tensor` now requires `.dtype` and `._untyped_storage` on storage objects). Documents fix approaches and current blocker status.
- `references/multi-node-90s-cluster-success.md` — the exact configuration and debugging timeline that finally brought the 2-node cluster online (using DP)
- `references/vllm-throughput-optimization.md` — systematic TTFT and throughput optimization: parameter combination matrix (max-num-batched-tokens × max-num-seqs), prefix cache testing, request-rate limiting, and compilation mode tradeoffs
Reference: `references/vllm-throughput-optimization.md` for systematic TTFT and throughput optimization: parameter combination matrix (max-num-batched-tokens × max-num-seqs), prefix cache testing, request-rate limiting, and compilation mode tradeoffs.

### Critical: FP8 Block Quantization Constraint

DeepSeek-V4-Pro uses FP8 weight quantization with `weight_block_size: [128, 128]`. Every TP-split dimension must be divisible by 128 (block_k).

Key dimensions:
- `moe_intermediate_size`: 3072
- `hidden_size`: 7168
- `q_lora_rank`: 1536

Working TP configs:
- **TP=4**: 3072/4=768 ✅, 7168/4=1792 ✅, 1536/4=384 ✅
- **TP=2**: All pass
- **TP=1**: No FP8 split needed
- **TP=8+**: **BLOCKED** — q_lora_rank 1536/8=192, 192%128=64 ❌

### DP+EP Architecture (4 nodes × 8 GPUs)

Since TP > 4 is blocked, use: **TP=4, DP=4, EP enabled** to utilize all 32 GPUs.

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

### Memory Budget (RTX 5090 32GB)
- Non-expert weights: ~19 GB/GPU
- Expert weights (FP4): ~12 GB/GPU
- Total: ~31 GB — tight fit on 32 GB

### Network Config (1 Gbps TCP, no RDMA)
```bash
export GLOO_SOCKET_IFNAME=ens20f0
export TP_SOCKET_IFNAME=ens20f0
export NCCL_SOCKET_IFNAME=ens20f0
export NCCL_IB_DISABLE=1
```

## Multi-Node DP (Data Parallel) Architecture

Multi-node vLLM can also use Data Parallelism (DP) instead of Pipeline Parallelism (PP). This is the architecture running on the 70.96+70.98 cluster.

### Architecture

```
Master (node-rank 0):  APIServer (port 8000) + EngineCore + GPU Workers
Worker  (node-rank 1):  EngineCore + GPU Workers (NO APIServer)
```

- Only the **master node** (node-rank 0) starts the HTTP API server
- Worker nodes run EngineCore + GPU Workers only — they do NOT listen on port 8000
- **curl to `localhost:8000` on a worker node will FAIL** — this is by design, not a failure

### Key Parameters

| Parameter | Purpose |
|-----------|---------|
| `--nnodes 2` | Total nodes in the cluster |
| `--node-rank 0/1` | Which node this is (0 = master with API) |
| `--master-addr <IP>` | Where the master's TCP store listens |
| `--master-port <PORT>` | TCP store port |
| `--data-parallel-size <N>` | Number of DP replicas across all nodes |
| `--data-parallel-size-local 1` | DP replicas per node |
| `--data-parallel-address <IP>` | This node's DP communication address |
| `--distributed-executor-backend mp` | Multi-processing executor |

Example (from the 70.96+70.98 cluster):
```bash
# Master node (70.96):
vllm serve /data/models/deepseekv4_pro \
  --host 0.0.0.0 --port 8000 \
  --distributed-executor-backend mp \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 1 \
  --data-parallel-size 2 --data-parallel-size-local 1 \
  --data-parallel-backend mp \
  --data-parallel-address 10.10.71.96 \
  --nnodes 2 --node-rank 0 \
  --master-addr 10.10.71.96 --master-port 29505 \
  --data-parallel-rpc-port 29550 \
  --enable-expert-parallel
```

**Critical: Worker nodes must set `--node-rank 1`.** If `--node-rank` is omitted, it defaults to 0 on all nodes, causing `HELLO message from remote engine 0, expected it to be local` — both nodes think they are rank 0, and the engine rejects the remote handshake. Always explicitly set `--node-rank 0` on master and `--node-rank 1` on each worker.

**Critical: `--nnodes` is required for all multi-node strategies, including PP.** Even in Pipeline Parallel (PP) mode with `--pipeline-parallel-size 2`, you MUST set `--nnodes 2`. Without it, vLLM computes `world_size = TP × PP = 16` and tries to use 16 GPUs on a single 8-GPU node, failing with:

```AssertionError: DP adjusted local rank 13 is out of bounds.```

This error comes from `vllm/v1/worker/gpu_worker.py` line 259-261 where `dp_local_rank * tp_pp_world_size + tp_local_rank` exceeds `accelerator.device_count()` (8). The fix is adding `--nnodes 2` so vLLM knows to distribute across nodes. PP also needs `--master-addr` and `--master-port` for cross-node TCPStore, plus the critical `VLLM_HOST_IP` env var set to each node's real IP.

### PP=2 Works Across 2 Nodes (ds4-sm120 branch)

PP=2 with `--nnodes 2` IS supported. The key env var is **`VLLM_HOST_IP`** — set it to each node's real network IP (e.g. 10.10.71.96 for master, 10.10.71.98 for worker). Without it, the multiproc executor uses loopback IP, causing `AssertionError: DP adjusted local rank 13 is out of bounds`.

Also required for PP across nodes:
- Full NCCL RoCE v2 config: `NCCL_IB_HCA=mlx5_0`, `NCCL_NET=IB`, `NCCL_SOCKET_IFNAME=ens35f0np0`, etc.
- `--nnodes 2 --node-rank <0|1>`
- `--master-addr <IP> --master-port <PORT>`
- Worker gets `--headless`

For the exact proven configuration, see the script `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` on 70.96.

### DP vs PP Tradeoffs (Updated for ds4-sm120 branch)

| Aspect | DP | PP |
|--------|----|----|
| **Inter-node bandwidth** | Only need metadata sync (lightweight) | Must ship activations (bandwidth-dependent) |
| **Prefix cache** | Moderate (44-47% improvement over no-cache) | **Excellent** (69% better TTFT than DP) |
| **Throughput** | Better TPOT (59ms vs 100ms) | Better TTFT (2.2s vs 3.3s) |
| **Startup time** | ~4-5 min (handshake overhead) | ~50s (no DP handshake) |
| **Memory** | Each replica holds full model weights (DP=2 halves per-node) | Each stage holds subset of layers |
| **Complexity** | More flags, ZMQ ports, potential handshake failures | Simpler — fewer inter-node flags |

**Mixed-GPU cluster limitation**: When nodes in a multi-node DP cluster have different GPU HBM capacities (e.g., 70.96 with 32 GB RTX 5090 vs 70.98 with 96 GB RTX PRO 6000), the EngineCore on the smaller-HBM node can fail during KV cache profiling even if the larger node succeeds. DeepSeek-V4-Pro's MoE model occupies ~90 GB per node for weights + routing table, leaving only 5–6 GB for KV cache on 96 GB cardsched. With `max-model-len=1048576` and FP8 KV cache, 24+ GiB is needed. The cluster will fail with: `ValueError: To serve at least one request with the models's max seq len (...), (XX GiB KV cache is needed, which is larger than the available KV cache memory (YY GiB).` The fix is always to reduce `max-model-len` to fit the **smallest** node's available memory, or ensure uniform GPU hardware across all nodes.

**Known Limitation: 5-Minute EngineCore Handshake Timeout (vLLM ds4-sm120 branch)**

In vLLM v0.6.0.dev0 (jasl/vllm `ds4-sm120` branch), the `startup_handshake` in `vllm/v1/engine/core.py` has a **hard-coded 300-second timeout** (`TimeoutError: Did not receive response from front-end process within 5 minutes`). This timeout CANNOT be extended via CLI flags.

**Root cause**: The `DPEngineCoreProc.__init__` path involves:
1. Model weight loading on all GPUs
2. KV cache memory profiling (`gpu_memory_utilization` scaling)
3. Torch Inductor compilation (mode=3)
4. Inter-node TCPStore handshake (if DP > 1 across nodes)

Any one of these exceeding 5 minutes triggers the timeout, even on a single-node DP=1 or DP=2 setup.

**Observed behavior** on the 70.96 (RTX 5090) cluster with DeepSeek-V4-Pro (806 GB model, FP8, 1048576 context length):
- With `--gpu-memory-utilization 0.93` and `--max-model-len 1048576`, the KVCache profiling phase alone takes 3-4 minutes
- Torch Inductor compilation (mode=3) adds 2-5+ minutes depending on model size and batch token range
- Combined, these reliably exceed the 300-second timeout

**Workarounds (in decreasing order of effectiveness)**:
1. **Reduce `max-num-batched-tokens`** — profiling and compilation cost scales with this value. Dropping from 32768 to 16384 can reduce initialization time below the 300-second threshold, while keeping `max-model-len` at 1048576. Each reduction roughly halves the compile_ranges_endpoints work. Combination `max-num-batched-tokens=16384` + `compile_ranges_endpoints=[8192,16384]` proved successful on a 2-node DP cluster with DeepSeek-V4-Pro.
2. **Reduce `max-num-seqs`** — from 512 to 256 reduces CUDA graph capture work, freeing a few GiB for KV cache. Does NOT affect KV cache sizing (that's driven by `max-model-len`), but can help when mixed GPU sizes exist in the cluster (e.g., 96 GB worker + 144 GB master).
3. **Reduce `max-model-len`** — shorter context → faster KV cache profiling (e.g., 524288 halves the profiling time)
4. **Reduce `gpu-memory-utilization`** — less memory to profile → faster initialization (e.g., 0.85 vs 0.93)
5. **Use single-node (DP=1)** — eliminates inter-node handshake overhead
6. **Set `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1`** — enables estimated (not exact) KV cache sizing, reducing profiling time
7. **Pre-warm compilation cache** — run a short inference request after first successful start; subsequent starts reuse cached compiled graphs
8. **Patch the timeout in source** — edit `vllm/v1/engine/core.py`, find `300` in the `startup_handshake` method and increase it

### Throughput Benchmarking

When running `vllm bench serve` against a remote server (no internet access), the benchmark tool attempts to download tokenizer from HuggingFace even when `--model` is a local path. Use `--tokenizer /path/to/model` to supply the local tokenizer and set `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`:

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
vllm bench serve --host localhost --port 8000 \
  --endpoint /v1/chat/completions \
  --backend openai-chat \
  --model deepseek_v4_pro \
  --tokenizer /data/models/deepseekv4_pro \
  --dataset-name random --input-len 1024 --output-len 256 \
  --num-prompts 10 --request-rate inf \
  --temperature 0 --disable-tqdm
```

**Critical:** The `--endpoint /v1/chat/completions` flag alone does NOT switch the request format — the benchmark still sends raw text completions. You MUST also set `--backend openai-chat` for the benchmark to generate proper chat-completion requests. Without this, all requests return `Bad Request`.

Typical throughput for DeepSeek-V4-Pro with TP=8, DP=2, EP=16, 2-node cluster:
- 128 input / 128 output (10 concurrent): ~0.82 req/s, ~105 tok/s, Mean TTFT=1585ms, Mean TPOT=84ms
- 1K input / 256 output (20 concurrent, via Python): ~1.1 req/s, ~285 tok/s

**Benchmark metric breakdown** (from `vllm bench serve` with `--backend openai-chat`):
- **TTFT (Time to First Token)** = prefilling time for the entire input batch. At 10 concurrent requests with 128 input tokens each: Mean TTFT ~1585ms (includes batch scheduling delay).
- **TPOT (Time Per Output Token)** = time per generated token after first. At 128 output tokens: ~84ms/token (~12 tok/s decode speed).
- **ITL (Inter-token Latency)** = time between successive tokens in streaming. ~83ms, close to TPOT.

For custom benchmarking of models with non-standard tokenizers on offline servers (where `vllm bench serve` may fail with `Bad Request` due to tokenizer mismatches), use a custom Python script with `requests` concurrent POSTs to `/v1/chat/completions` — this bypasses the built-in tokenizer loading entirely and lets the server handle its own tokenization.

**Negative evidence**: `max-num-batched-tokens=32768` with all defaults (max-num-seqs=512, gpu-memory-utilization=0.93) reliably exceeds the 5-minute timeout on a 2-node DP cluster, even without SSH or hosts issues. Dropping to 16384 succeeds. The parameter is the single most impactful lever for startup time.

**Secondary workaround for log visibility**: When vLLM spawns multiple API server processes (`api_server_count > 1` via `--data-parallel-size` defaulting), it auto-disables stats logging with `disabling stats logging to avoid incomplete stats`. Add `--api-server-count 1` to restore the periodic `Avg prompt throughput` / `Avg generation throughput` log lines. Trade-off: single API server can bottleneck at very high QPS; the `/metrics` endpoint still provides aggregate stats regardless.

### Diagnostics for Multi-Node DP

When investigating "is the server alive" in a DP cluster:

1. **Check master node** — only the master has the HTTP API:
   ```bash
   curl -s http://<master-ip>:8000/health
   ```
   Returns `200 OK` if the API server is running.

2. **Verify with a real inference request** — `/health` only checks the HTTP server, not the engine:
   ```bash
   curl -s -X POST http://<master-ip>:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"<model-name>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
   ```

3. **Metrics on worker node** — check if EngineCore and GPU Workers are running via `ps aux`:
   ```bash
   ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker'
   ```

4. **Check inter-node connectivity** — ping between the dedicated inter-node IPs:
   ```bash
   ping -c 2 <master-addr>
   ```

5. **Check logs on master node** — look for successful request responses (200 OK):
   ```bash
   tail -f /tmp/vllm*.log | grep "200 OK"
   ```

6. **Check GPU utilization** — all GPUs should be near 100% if the model is loaded:
   ```bash
   nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
   ```

## GLM-5.1 Reasoning / Thinking Mode

GLM-5 and GLM-5.1 have thinking mode **enabled by default**. No client parameter needed to activate it.

### Server-Side (vLLM)

```bash
vllm serve zai-org/GLM-5.1-FP8 \
     --tensor-parallel-size 8 \
     --reasoning-parser glm45 \
     --tool-call-parser glm47 \
     --enable-auto-tool-choice \
     --chat-template-content-format=string \
     --served-model-name glm-5.1-fp8
```

- `--reasoning-parser glm45` — required to extract reasoning content into the `reasoning` response field
- `--tool-call-parser glm47` — for tool calling support
- Thinking is ON by default; no `--default-chat-template-kwargs` needed

### Client-Side Controls

| Action | Parameter |
|--------|-----------|
| Read thinking output | `response.choices[0].message.reasoning` |
| Reduce thinking depth | `extra_body={"reasoning_effort": "high"}` (default is `"max"`) |
| Disable thinking | `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` |
| Thinking token budget | `extra_body={"chat_template_kwargs": {"enable_thinking": True, "thinking_token_budget": 1024}}` |
| Standard OpenAI reasoning_effort | `reasoning_effort="high"` (vLLM 0.19.0+ auto-maps to `enable_thinking=true`) |

### GLM-5.1 `reasoning_effort` Levels

GLM-5/5.1 supports two thinking effort levels via `reasoning_effort`:

| Level | Behavior |
|-------|----------|
| `"max"` | **Default**. Maximum thinking depth. Used when `reasoning_effort` is unset or any value other than `"high"`. |
| `"high"` | Reduced thinking, faster responses, fewer thinking tokens. Must be explicitly set. |

Usage:
```python
# High effort (faster, less thinking)
resp = client.chat.completions.create(
    model="glm-5.1-fp8",
    messages=[...],
    extra_body={"reasoning_effort": "high"},
)

# Max effort (default, no parameter needed)
resp = client.chat.completions.create(
    model="glm-5.1-fp8",
    messages=[...],
)
```

### Server-Level Thinking Defaults

Control thinking for ALL requests without client-side changes:

```bash
# Disable thinking by default (clients can override per-request)
vllm serve zai-org/GLM-5.1-FP8 \
    --reasoning-parser glm45 \
    --default-chat-template-kwargs '{"enable_thinking": false}'

# Enable thinking by default (for models where it's off by default, e.g. Granite, DeepSeek-V3.1)
vllm serve ibm-granite/granite-3.2-2b-instruct \
    --reasoning-parser granite \
    --default-chat-template-kwargs '{"thinking": true}'
```

Request-level `chat_template_kwargs` always override server defaults.

### Hermes Custom Provider Note

When serving GLM-5.1 as a custom provider in Hermes Agent, `reasoning_effort` in `config.yaml` does NOT auto-inject `chat_template_kwargs` into API calls. The `chat_completions` transport only sends reasoning params for providers with `supports_reasoning=True` (OpenRouter, Nous Portal, etc.). Since GLM-5.1 thinking is ON by default, this is not a problem — but to explicitly toggle thinking per-request, pass `chat_template_kwargs` via `extra_body_additions` in config or modify the transport code.

### vLLM Reasoning Effort Auto-Mapping

vLLM (0.19.0+) auto-maps OpenAI-style `reasoning_effort` to `enable_thinking`:
- `"low"` / `"medium"` / `"high"` → `enable_thinking = true`
- `"none"` → `enable_thinking = false`
- Not set → no injection, preserves model default

This is generic across all reasoning models (GLM, Qwen3, DeepSeek, Granite, etc.).

## DeepSeek-V4-Flash Single-Node Deployment

DeepSeek-V4-Flash is a 292B MoE model (256 routed experts, 6 active, hidden_size=4096, 43 layers, moe_intermediate_size=2048) with FP8 weights, 46 safetensors (~149G total). Fits on a single 8×GPU node with 96GB cards.

### Start Script

- **70.88**: `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`
- **70.98**: `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`

Key parameters (TP=8): EP enabled, `--kv-cache-dtype fp8`, `--block-size 256`, `--reasoning-parser deepseek_v4`, `--tool-call-parser deepseek_v4`, `--tokenizer-mode deepseek_v4`, `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", "custom_ops":["all"]}'`

**Model path issue on 70.98:** The script hardcodes `MODEL_PATH="/home/jianliu/work/models/deepseekv4_flash"` which does not exist on 70.98. Update to `MODEL_PATH="/data/models/deepseekv4_flash"` after the model copy completes.

**Bug fixed:** `MAX_LEN=1,048,576` contained commas (bash literal string). Fixed to `MAX_LEN=1048576` on 2026-06-17.

### Adaptive TP Script (70.98)

The script at `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh` on 70.98 was updated (2026-06-17) to support partial-GPU deployment:

1. **`CUDA_VISIBLE_DEVICES`** — Added with commented presets for 2/4/6/8 GPUs. Defaults to all 8 if unset.
2. **`TP_SIZE` auto-detection** — `TP_SIZE=$(echo "$CUDA_VISIBLE_DEVICES" | tr ',' '\n' | wc -l)` automatically matches GPU count.
3. **Echo line** — Updated to print actual TP and GPU list: `echo "=== DeepSeek-V4-Flash SINGLE NODE (TP=${TP_SIZE}, GPUs=${CUDA_VISIBLE_DEVICES}) ==="`
4. **Usage**: `CUDA_VISIBLE_DEVICES=0,1,2,3 bash start_dsv4_flash_1node.sh` or uncomment a line in the script.

### Model Locations

| Server | Path | Status |
|--------|------|--------|
| 70.88 | `/home/jianliu/work/models/deepseekv4_flash/` | Source (149G, 46 safetensors) |
| 70.98 | `/data/models/deepseekv4_flash/` | **Complete** (46/46 shards, 149 GB, rsync finished 2026-06-17) |

### Partial GPU Deployment (Fewer than 8 GPUs)

To run DeepSeek-V4-Flash on a subset of GPUs (e.g., for testing or when memory is constrained), modify three things in the startup script:

1. **`CUDA_VISIBLE_DEVICES`** — Set before `vllm serve` to select which GPUs to use:
   ```bash
   export CUDA_VISIBLE_DEVICES=0,1,2,3   # Use 4 GPUs
   ```

2. **`--tensor-parallel-size`** — Must match the number of GPUs listed:
   ```bash
   TP_SIZE=4   # Must equal len($CUDA_VISIBLE_DEVICES)
   ```

3. **`--max-model-len`** — Reduce proportionally to fit KV cache in fewer GPUs:
   - TP=8: 1,048,576 (1M tokens)
   - TP=6: ~524,288 (512K)
   - TP=4: ~262,144 (256K)
   - TP=2: ~131,072 (128K)

4. **No other changes needed** — These single-node settings do NOT need modification:
   - `NCCL_IB_DISABLE=1` — Correct for single-node (NVLink intra-node)
   - `NCCL_SOCKET_IFNAME=ens20f0` — Harmless on single-node
   - `--enable-expert-parallel` — EP auto-scales with TP (256 experts / TP GPUs)
   - `--enable-ep-weight-filter` — Keep as-is

5. **Remove cross-node config** (if copying from a 2-node script): Delete all `MASTER_ADDR`, `VLLM_HOST_IP`, `--nnodes`, `--node-rank`, `--headless`, `NCCL_IB_HCA`, `NCCL_NET`, `DP_` variables, `data-parallel-*` flags. Single-node only needs NVLink (auto-detected).

### Memory Estimates by TP (RTX PRO 6000 96GB)

| TP | Weights/GPU | Available KV Cache | Recommended max-model-len |
|----|-------------|-------------------|--------------------------|
| 8  | ~20 GB      | ~74 GB            | 1,048,576                |
| 6  | ~26 GB      | ~68 GB            | ~524,288                 |
| 4  | ~39 GB      | ~55 GB            | ~262,144                 |
| 2  | ~78 GB      | ~15 GB            | ~131,072                 |

These are rough estimates with `--gpu-memory-utilization 0.92`. Actual capacity depends on expert parallelism savings and CUDA graph overhead.
| 70.96 | `/data/models/deepseekv4_flash/` | Empty dir (4.4M only — needs fresh copy) |
| 70.95 | — | Only has deepseekv4_pro |
| 70.93 | — | No SSH access (password required) |

### rsync `-t` Flag Preserves Source mtime

When using `rsync -a` or `rsync -t`, the `-t` flag preserves the source file's modification timestamp on the destination. This means `ls -l` on the destination shows the **source's original mtime**, not the copy time. A file dated "April 28" on the destination was likely copied months later — the date tells you when the source created it, not when the transfer happened. To see actual transfer progress, use shard count (`ls model-*.safetensors | wc -l`) and `du -sh`, not file dates.

### Partial GPU Deployment

To run DeepSeek-V4-Flash on fewer than 8 GPUs, set `CUDA_VISIBLE_DEVICES` and reduce `TP_SIZE` and `MAX_LEN` proportionally:

```bash
export CUDA_VISIBLE_DEVICES=0,1,2,3   # Use 4 GPUs
TP_SIZE=4
MAX_LEN=524288                         # Reduce from 1M proportionally
```

VRAM budget per GPU (96GB RTX PRO 6000 Blackwell):

| TP | Weight/GPU | Free for KV | Practical Max Len | Viable? |
|----|-----------|-------------|---------------------|---------|
| 8 | ~19GB | ~69GB | 1,048,576 (1M) | ✅ original |
| 4 | ~37GB | ~51GB | 262,144–524,288 | ✅ |
| 2 | ~74GB | ~14GB | 65,536–131,072 | ⚠️ tight |
| 1 | ~149GB | OOM | — | ❌ |

When running multiple vLLM instances on the same node (e.g., V4-Flash + GLM-5.1), use non-overlapping `CUDA_VISIBLE_DEVICES` and different `--port` values.

### Network Transfer Bottleneck: 70.88

70.88's management NIC `ens20f0` auto-negotiates at **100 Mb/s** (not 1 GbE), capping all network transfers at ~5-6 MB/s. This is the bottleneck for any file copy to/from 70.88. Other nodes (70.96, 70.98) also have `ens20f0` at 100 Mb/s — this is a cluster-wide pattern. The 100 GbE bond0 NICs (`ens35f0np0`/`ens35f1np1` on 70.88, `bond0` on 70.98) are RDMA-capable but not SSH-routable by default. To bypass the 100 Mb/s bottleneck for file transfers, use the bond0/192.168.66.x network: `rsync -aP --partial source/ jianliu@192.168.66.20:/data/models/dest/`.

## GLM-5.1-FP8 Multi-Node Deployment

Reference: `references/glm5-multi-node.md` for detailed GLM-5.1-FP8 deployment. Also see the dedicated `glm5-fp8-blackwell` skill for the complete deployment reference including patches, backend selection table, and debugging history. — architecture (DeepSeek V2-style MLA with 256 experts, FP8 quantized), parallelism strategy (TP=8, PP=2, EP=8), memory budget (64K context on 96 GB Blackwell cards), and the critical MLA/Blackwell compatibility issue.

### Key Differences from DeepSeek V4 Pro

| Aspect | DeepSeek V4 Pro | GLM-5.1-FP8 |
|--------|----------------|--------------|
| Model type | `deepseek_v4` | `glm_moe_dsa` → deepseek_v2 |
| Tokenizer | `--tokenizer-mode deepseek_v4` | Auto-detected from config |
| Tool-call parser | `--tool-call-parser deepseek_v4` | N/A |
| Reasoning parser | `--reasoning-parser deepseek_v4` | N/A |
| Transformers req | v4 compatible | **v5.4.0+ required** |
| Max context | 1048576 (1M) | 65536 (practical limit) |

### Critical: Transformers v5 Required

The `glm_moe_dsa` model type is NOT recognized by transformers v4.x. Before starting vLLM, upgrade:
```bash
pip install --upgrade 'transformers>=5.4.0'
```

See `references/glm5-multi-node.md` for full details.

### Kv Cache dtype: `fp8` required with TRITON_MLA on Blackwell

On Blackwell (CC 12.0), `TRITON_MLA` with `--kv-cache-dtype auto` (bf16) triggers the FlashInfer XQA MLA fallback which rejects non-fp8 inputs: `XQA MLA only supports fp8 operation on SM120/SM121 GPUs`. Always use `--kv-cache-dtype fp8` with `TRITON_MLA` on Blackwell.

### Triton Runtime JIT Shared Memory Trap

The Triton MLA decode kernel `_fwd_kernel_stage2` is JIT-compiled during the **first inference request, not during startup**. This means CUDA graph warmup can succeed, the server can start and serve `/health`, but the first real chat completion request will fail at decode time with `OutOfResources: shared memory, Required: 102400, Hardware limit: 101376`. Fix: `--enforce-eager` to skip the Triton JIT decode kernel entirely.

### Known Blocker: `wk_weights_proj.weight` KeyError During Weight Loading

After passing the attention backend selection (requires CC 12.0 patches — see below), GLM-5.1-FP8 weight loading fails with:
```
KeyError: 'model.layers.39.self_attn.indexer.wk_weights_proj.weight'
```

**Root cause**: vLLM's `_try_load_fp8_indexer_wk` function in `deepseek_v2.py` tries to dequantize FP8 `wk.weight` + `wk.weight_scale_inv` and store into a fused `wk_weights_proj.weight` parameter. The GLM checkpoint stores `wk` as FP8 with `weight_scale_inv`, and the fused param buffer may not exist in `params_dict` at the time the function runs.

**Status**: Unresolved — vLLM `ds4-sm120` branch does not handle GLM's FP8 indexer weight layout correctly. Two possible fixes:
1. Patch `_try_load_fp8_indexer_wk` to gracefully fall through to the `stacked_params_mapping` path when `params_dict[fused_name]` is missing
2. The GLM checkpoint may need its weight format adjusted (e.g., `wk` stored as BF16 instead of FP8) to match what DeepSeek V4 checkpoints provide

### Blackwell CC 12.0 MLA Backend Patches

Deploying GLM-5.1-FP8 (or any MLA model) on Blackwell GPUs requires patching vLLM's attention backend code. See `references/glm5-multi-node.md` for the exact patches needed across 8+ source files and the critical step of clearing Python bytecode cache after patching. Also see `vllm-tuning` skill's `references/blackwell-mla-patches.md` for a standalone patch reference.

### `is_v32` Sparse Attention: `hasattr` vs Truthy Check

Models with `index_topk` in config.json (e.g., DeepSeek V3/V4/V32, GLM-5.1-FP8, Kimi K2) trigger sparse MLA via `is_v32` in `deepseek_v2.py`:

```python
# Default behavior (problematic):
self.is_v32 = hasattr(config, "index_topk")
```

Setting `index_topk` to `None` or `0` via `--hf-overrides` still passes `hasattr`. **The only way to disable sparse** is to patch the source to also check truthiness:

```python
self.is_v32 = hasattr(config, "index_topk") and getattr(config, "index_topk", 0) > 0
```

Then `--hf-overrides '{"index_topk": 0}'` actually disables sparse. Without the patch, `index_topk: 0` leaves `use_sparse=True` and triggers a cascade of failures: FLASHINFER_MLA_SPARSE auto-selection -> 3D page table issues or XQA query-head mismatches.

When `is_v32=False`, the model also lacks the `indexer` submodule. Checkpoint weights containing `indexer` in their name must be skipped during `load_weights` — add a guard: `if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name): continue`.

## General Model Serving Principles

1. **Tensor parallelism scaling** — limited by smallest divisible dimension and inter-node bandwidth
2. **Pipeline parallelism** — better for multi-node when TP hits constraints and DP is not feasible
3. **Expert parallelism (EP)** — essential for Mixture-of-Experts models across many GPUs
4. **Data parallelism (DP)** — use when TP/PP saturated, for throughput scaling; only master node exposes HTTP API

## Pitfalls

- **NCCL "unhandled system error" on Blackwell (sm120)** — NCCL 2.28.9 on RTX PRO 6000 Blackwell SE can enter a bad state after repeated vLLM process kills, producing `RuntimeError: NCCL error: unhandled system error` during `PyNcclCommunicator.__init__`. All 8 workers fail simultaneously. The IB link is ACTIVE, no zombie processes exist. **Fix**: GPU reset (`nvidia-smi -r`, needs root) or system reboot. Temporary workaround: set `NCCL_IB_DISABLE=1 NCCL_NET=Socket` to use TCP fallback. See the vllm-tuning skill for full details.
- **Multi-node DP REQUIRES SSH key auth between all nodes** — vLLM EngineCore handshake uses SSH to coordinate DP initialization. Without passwordless SSH in both directions, the handshake silently hangs until the 5-minute hard timeout (`RuntimeError: Did not receive response from front-end process within 5 minutes`). Before debugging any multi-node DP failure, always verify: `ssh <user>@<remote-node> "hostname"` succeeds without password from EVERY node in the cluster. SSH keys can expire or be overwritten during OS updates — re-check this first, not last.
- **`--api-server-count 1` must NOT be set on headless worker nodes** — `--headless` nodes cannot have API servers. The error is explicit: `--api-server-count=1 cannot be used with --headless (no API servers are started in headless mode).` Only the master node (node-rank 0) should set `--api-server-count`. If omitted entirely, vLLM defaults `api_server_count` to `data_parallel_size`, which works (2 API servers on master, 0 on headless).
- **`/health` is shallow** — it returns 200 even if the engine is stuck. Always follow up with a real chat completion to verify end-to-end operation.
- **PyTorch 2.11+ breaks local-format `.pth` files with persistent ID tuples** — models stored as `torch.save(dict_of_tensors)` use a 5-tuple persistent ID `('storage', cls, key, device, size)`. PyTorch 2.11's `_rebuild_tensor` accesses `storage.dtype` and `storage._untyped_storage.device` on this tuple, both absent. Fix: return a TypedStorage or wrapper object from `persistent_load` with both attributes. See `references/wan22-t2v-local-model.md`.
- **PyTorch 2.11+ breaks local-format `.pth` files with persistent ID tuples** — models stored as `torch.save(dict_of_tensors)` use a 5-tuple persistent ID `('storage', cls, key, device, size)`. PyTorch 2.11's `_rebuild_tensor` accesses `storage.dtype` and `storage._untyped_storage.device` on this tuple, both absent. Fix: return a TypedStorage or wrapper object from `persistent_load` with both attributes. See `references/wan22-t2v-local-model.md`.
- **5-minute EngineCore handshake timeout is hard-coded in vLLM** — see the "Known Limitation" section above for details and workarounds.
- **FP8 + TP + EP alignment (single-node MoE)**: On single-node MoE models with FP8 weight quantization, combining TP + EP can produce `input_size_per_partition = 64` (not divisible by FP8 `block_k = 128`). All workers crash simultaneously with `ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128`. This happens when TP sharding and EP expert sharding both act on the same weight dimension. Workaround: use DP instead of EP, or remove `--enable-ep-weight-filter` (EP still active without weight filtering). DP=8 avoids the conflict because TP=1 per rank. Multi-node PP+EP does not hit this because EP=8 vs single-node EP=8 with TP=8.
- **DP coordinator address** — `--data-parallel-address` must be set on the head node to avoid TCPStore connection failures
- **hostname resolution** — if hostname resolves to 127.0.1.1, explicitly set `NCCL_SOCKET_IFNAME`
- **1 Gbps TCP is slow** for model weight broadcast during DP — expect longer startup times
- **`/health` is shallow** — it returns 200 even if the engine is stuck. Always follow up with a real chat completion to verify end-to-end operation.
- **PyTorch 2.11+ breaks local-format `.pth` files with persistent ID tuples** — models stored as `torch.save(dict_of_tensors)` use a 5-tuple persistent ID `('storage', cls, key, device, size)`. PyTorch 2.11's `_rebuild_tensor` accesses `storage.dtype` and `storage._untyped_storage.device` on this tuple, both absent. Fix: return a TypedStorage or wrapper object from `persistent_load` with both attributes. See `references/wan22-t2v-local-model.md`.
- **PyTorch 2.11+ breaks local-format `.pth` files with persistent ID tuples** — models stored as `torch.save(dict_of_tensors)` use a 5-tuple persistent ID `('storage', cls, key, device, size)`. PyTorch 2.11's `_rebuild_tensor` accesses `storage.dtype` and `storage._untyped_storage.device` on this tuple, both absent. Fix: return a TypedStorage or wrapper object from `persistent_load` with both attributes. See `references/wan22-t2v-local-model.md`.