---
name: remote-server-70-88
description: Remote GPU server management for 10.10.70.88 (oem88) — 8× NVIDIA GeForce RTX 5090 32GB (SM 12.0 Blackwell), CUDA 13.0, vLLM + TRTLLM + SGLang serving, proxy access, SSH and operations.
---

# Remote Server 70.88 (oem88)

## Hardware Specs

| Item | Value |
|------|-------|
| Hostname | 10.10.70.88 |
| GPUs | 8× NVIDIA GeForce RTX 5090 32GB (SM 12.0 Blackwell, device 10de:2b85) |
| CUDA | 13.0 |
| Driver | 580.159.03 |
| CPU | 2× Xeon Platinum 8558P (48c/96t per socket, 260 MB L3 per socket, 192 threads total) |
| NCCL | 2.28.9+cuda13.0 |
| SSH | `ssh jianliu@10.10.70.88` |

## Environment

**ALWAYS `source ~/.bashrc`** before pip/npm operations — contains proxy and HF_ENDPOINT settings.

```bash
# Standard pattern for all remote commands
ssh jianliu@10.10.70.88 "source ~/.bashrc && <command>"
```

Proxy: `10.10.60.140:7890` (http/https), configured in `~/.bashrc`.

**venv path**: `/data/venvs/vllm-ds4/` — note the **plural** `venvs/`. `/data/venv/` (singular) does not exist.
**SGLang venv**: `/data/venvs/sglang-wan-nvfp4/` — the working SGLang install for wan2.2 uses this separate venv, not `vllm-ds4/`. Verify which venv a script uses before running.

## Installed Packages

Python 3.12.13, torch 2.11.0+cu130, SGLang 0.5.12, safetensors 0.8.0rc1.

## TWO SGLang VEnvs on This Server

This server has **two separate SGLang deployments** — do not conflate them:

| Venv | Path | Used By |
|------|------|---------|
| sglang-wan-nvfp4 | `/data/venvs/sglang-wan-nvfp4/` | `generate` CLI, official test scripts in `~/work/bench_test/wan_2_2_nvfp4/` |
| vllm-ds4 | `/data/venvs/vllm-ds4/` | Manual serving, ad-hoc testing (SGLang 0.5.12 installed here) |

**Always use the correct venv for the task.** The `generate` command and benchmark scripts in `~/work/bench_test/wan_2_2_nvfp4/` use `sglang-wan-nvfp4`, not `vllm-ds4`.

## GPU Topology & NCCL Performance

- **NUMA 0** — GPU0-3 (CPU 0-47,96-143)
- **NUMA 1** — GPU4-7 (CPU 48-95,144-191)
- **Cross-NUMA** — SYS (PCIe + UPI)
- **No NVLink** — RTX 5090 has no NVLink; PCIe Gen5 ×16 only
- **PCIe class**: 0300 (VGA) — differs from RTX PRO 6000 (0302 = 3D controller)
- **NICs**: mlx5_0, mlx5_1 on NUMA1

### Alltoall Benchmark (2026-06-22, vs 70.98)

| Metric | 4-GPU | 8-GPU | 8/4 ratio |
|--------|------:|------:|----------:|
| Peak busbw | 35.46 GB/s | 25.25 GB/s | 0.71x |
| Avg busbw | 9.60 GB/s | 5.71 GB/s | 0.59x |

70.88's 8-GPU alltoall retains 71% of 4-GPU performance, vs only 38% on 70.98 (Xeon Gold 6530 + NCCL 2.30.4). The Platinum 8558P's 50% more cores and 62% more L3 cache, combined with NCCL 2.28.9's better cross-NUMA tuning for the RTX 5090 (device 10de:2b85), explain the gap. See `references/nccl-benchmark-results.md` in the `remote-server-management` skill for full per-size data and root cause analysis.

## Network

Proxy-enabled server — PyPI and HuggingFace accessible via `~/.bashrc` proxy settings.
Use **Tsinghua Tuna mirror** (`-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30`) for faster, more reliable pip installs on this server.

### Management NIC Speed Bottleneck

**`ens20f0` is connected at 100 Mb/s (Fast Ethernet)** — NOT 1 GbE. This is the primary management NIC (10.10.70.88/24) used for all SSH and rsync traffic. Effective throughput is ~5-6 MB/s, severely limiting large model transfers.

| NIC | Status | Speed | Purpose |
|-----|--------|-------|---------|
| `ens20f0` | UP | **100 Mb/s** ← bottleneck | Management (10.10.70.88/24) |
| `ens35f0np0` | DOWN | — | High-speed (100GbE, not active) |
| `ens35f1np1` | DOWN | — | High-speed (100GbE, not active) |

Model copies from 70.88 to other nodes (e.g., rsync to 70.98) are capped at ~5.3 MB/s. A 149G model transfer takes ~8 hours. This may be an auto-negotiation fallback — check `ethtool ens20f0` and consider forcing 1 GbE if the switch supports it.

> See `references/wan22_nvfp4_20260609.md` for Wan2.2 OOM analysis, generate.log error chain, and benchmark test dir reference.

**Model copy to 70.98:** DeepSeek-V4-Flash (149G, 46 safetensors) at `/home/jianliu/work/models/deepseekv4_flash/`. Transfer to 70.98 at `/data/models/deepseekv4_flash/` via rsync at ~5 MB/s (bottleneck: ens20f0 100 Mb/s). Monitor: `ssh jianliu@10.10.70.98 "du -sh /data/models/deepseekv4_flash/"`

## Docker-based vLLM Serving (70.88)

A Docker-based vLLM server is available for Qwen3.6-35B-A3B-NVFP4 (as of 2026-06-21):

```bash
docker run -d --gpus '"device=0,1"' \
  -v /data/models/Qwen3.6-35B-A3B-NVFP4:/model:ro \
  -p 8000:8000 vllm/vllm-openai:nightly \
  --model /model --tensor-parallel-size 2 --trust-remote-code \
  --quantization modelopt --kv-cache-dtype fp8 --moe-backend marlin \
  --load-format fastsafetensors --gpu-memory-utilization 0.80 \
  --max-num-batched-tokens 8192 --enable-chunked-prefill \
  --language-model-only --reasoning-parser qwen3 --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'
```

- **Served model ID**: `/model` (mounted read-only from host path `/data/models/Qwen3.6-35B-A3B-NVFP4`)
- **GPU**: 2× RTX 5090 (TP=2), `--gpu-memory-utilization 0.80`
- **Quantization**: modelopt NVFP4, Marlin MoE backend, FP8 KV cache
- For benchmarking: use `SERVED_MODEL_NAME=/model` and `TOKENIZER=/data/models/Qwen3.6-35B-A3B-NVFP4`
- Docker image: `vllm/vllm-openai:nightly` (installed 2026-06-21 via deb packages)

## DeepSeek V4 Flash Single-Node Serving

Startup script: `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh` — TP=8, EP=8, max_len=16384, FP8 KV cache, `FLASHINFER_DISABLE_VERSION_CHECK=1`.

Bench dir (legacy): `/home/jianliu/work/bench_test/deepseekv4_flash/` (start script + throughput test + benchmark wrapper).

## Qwen3.6-35B-A3B-FP8 Single-Node TP8+EP

Startup: `/home/jianliu/work/bench_test/qwen_3_6/start_qwen36_1node.sh` — TP=8, EP enabled, gpu_mem=0.92.

Bench dir: `/home/jianliu/work/bench_test/qwen_3_6/`.

**Note: FP8 + TP8 + EP alignment issue on single-node.** When TP=8 splits weights and EP further shards experts, the resulting `input_size_per_partition=64` is NOT divisible by FP8's `block_k=128`. This crashes all 8 workers simultaneously with `ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128`. Workaround: remove `--enable-ep-weight-filter` (EP still enabled without weight filtering). DP=8 works because TP=1 per rank avoids the TP-split dimension conflict.

```bash
# Start (background)
ssh jianliu@10.10.70.88 "source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate && \\
  export NCCL_SOCKET_IFNAME=ens20f0 && export NCCL_IB_DISABLE=1 && \\
  export VLLM_ENGINE_READY_TIMEOUT_S=3600 && \\
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True && \\
  export FLASHINFER_DISABLE_VERSION_CHECK=1 && \\
  nohup vllm serve /home/jianliu/work/models/deepseekv4_flash \\
    --host 0.0.0.0 --port 8000 \\
    --tensor-parallel-size 8 \\
    --gpu-memory-utilization 0.92 \\
    --trust-remote-code \\
    --kv-cache-dtype fp8 \\
    --block-size 256 \\
    --enable-expert-parallel \\
    --enable-ep-weight-filter \\
    --tokenizer-mode deepseek_v4 \\
    --tool-call-parser deepseek_v4 \\
    --enable-auto-tool-choice \\
    --reasoning-parser deepseek_v4 \\
    --max-model-len 16384 \\
    --compilation-config '{\"cudagraph_mode\":\"FULL_AND_PIECEWISE\", \"custom_ops\":[\"all\"]}' \\
    > /data/vllm_dsv4_flash_1node.log 2>&1 &"
```

**Health check:**
```bash
ssh jianliu@10.10.70.88 "curl -s http://localhost:8000/v1/models 2>&1 | head -3"
```

**Test completion:**
```bash
ssh jianliu@10.10.70.88 "curl -s --max-time 30 http://localhost:8000/v1/completions \\
  -H 'Content-Type: application/json' \\
  -d '{\"model\":\"/home/jianliu/work/models/deepseekv4_flash\",\"prompt\":\"What is 2+2?\",\"max_tokens\":8}'"
```

**Known issues during startup:**
- `flashinfer-jit-cache` vs `flashinfer` version mismatch → set `FLASHINFER_DISABLE_VERSION_CHECK=1`
- `ModuleNotFoundError: No module named 'flash_attn.ops'` → the vllm-ds4-sm120 fork has its own flash attention; patched `rotary_embedding/common.py` to fall back to `vllm.vllm_flash_attn.ops.triton.rotary` when `flash_attn.ops` is absent. Patch at `/data/vllm-ds4-sm120/vllm/model_executor/layers/rotary_embedding/common.py`.
- `KV cache memory too small` at 0.88 utilization → raise to 0.92 (model weights ~160 GiB across 8 GPUs with EP)

Check status:
```bash
ssh jianliu@10.10.70.88 "source ~/.bashrc && ps aux | grep vllm | grep -v grep"
ssh jianliu@10.10.70.88 "source ~/.bashrc && curl -s http://localhost:8000/v1/models 2>&1 | head -3"
```

Log: `/data/vllm_dsv4_flash_1node.log`

## SGLang Serving

**Two separate SGLang venvs exist on 70.88:**
- `/data/venvs/vllm-ds4/` — vLLM fork venv, SGLang 0.5.12 installed here
- `/data/venvs/sglang-wan-nvfp4/` — dedicated SGLang Wan venv (used by `generate.py`)

User scripts like `generate.py` use the `sglang-wan-nvfp4` venv, NOT `vllm-ds4`.

SGLang 0.5.12 is installed in `/data/venvs/vllm-ds4/`.

**Start SGLang server** (use `sglang-wan-nvfp4` venv):
```bash
MODEL_PATH=/data/models/wan2.2_t2v_A14B_diffusers_nvfp4

ssh jianliu@10.10.70.88 "source ~/.bashrc && \
/data/venvs/sglang-wan-nvfp4/bin/python -m sglang.distributed.launch_server \
  --model-path $MODEL_PATH \
  --port 30000 \
  --host 0.0.0.0 \
  --mem-fraction-static 0.88 \
  --max-running-req 64 2>&1 | tee /data/sglang_server.log"
```

**Health check:**
```bash
curl http://10.10.70.88:30000/v1/models
curl http://10.10.70.88:30000/Health
```

**SGLang streaming chat example:**
```bash
curl http://10.10.70.88:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"wan2.2","messages":[{"role":"user","content":"hello"}],"max_tokens":128}' \
  --max-time 60
```

## TRTLLM Serving

### Status: NOT YET INSTALLED

Blocked by dependency conflict. To install:

```bash
# Step 1: Pin fsspec to resolve datasets constraint
ssh jianliu@10.10.70.88 "source ~/.bashrc && \
  /data/venvs/vllm-ds4/bin/pip install 'fsspec==2024.9.0' \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30"

# Step 2: Install tensorrt core
ssh jianliu@10.10.70.88 "source ~/.bashrc && \
  /data/venvs/vllm-ds4/bin/pip install tensorrt==11.0.0.114 \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30"

# Step 3: Install TRTLLM without deps (deps handled separately)
ssh jianliu@10.10.70.88 "source ~/.bashrc && \
  /data/venvs/vllm-ds4/bin/pip install tensorrt-llm==1.2.1 --no-deps \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30"
```

Verify:
```bash
ssh jianliu@10.10.70.88 "source ~/.bashrc && \
  /data/venvs/vllm-ds4/bin/python -c 'import tensorrt; print(tensorrt.__version__)'"
ssh jianliu@10.10.70.88 "source ~/.bashrc && \
  /data/venvs/vllm-ds4/bin/python -c 'import tensorrt_llm; print(tensorrt_llm.__version__)'"
```

**Note**: TRTLLM pre-built wheels target SM 8.x (Ampere/Ada). RTX 5090 is SM 9.0 (Blackwell) — NVIDIA may not yet ship pre-built wheels for SM 9.0 + CUDA 13.0. May require building from source.

**70.88 benchmark results — Qwen3.6-35B-A3B-NVFP4, TP=2, single-batch (concurrency=1):**

Config: 2048 input tokens, 500 output tokens, 20 requests, concurrency=1, request-rate=inf

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | Mean E2EL (ms) | Duration (s) |
|-----------|-------------|-------------|----------------|----------------|----------------|-------------|
| 0% | 261.0 | 1390.5 | 114.1 | 3.61 | 1915.2 | 38.3 |
| 40% | 259.8 | 1372.5 | 113.4 | 3.63 | 1924.0 | 38.5 |
| 80% | 261.1 | 1374.6 | 111.5 | 3.61 | 1914.7 | 38.3 |

Key finding: Single-batch (conc=1) shows NO cache hit rate benefit — throughput, TTFT, TPOT, and E2E latency are nearly identical across 0%/40%/80% cache. With concurrency=1, requests are sequential so there's no cross-request KV cache prefix reuse.

Results directory: `70.88:.../vllm_bench_results/20260621_122441/`

## Common Operations

```bash
# GPU status
ssh jianliu@10.10.70.88 nvidia-smi

# GPU topology
ssh jianliu@10.10.70.88 nvidia-smi topo -m

# Disk space
ssh jianliu@10.10.70.88 "df -h /data/"

# Model completeness check (wan2.2: 7 safetensors expected)
ssh jianliu@10.10.70.88 "find /data/models/wan2.2_t2v_A14B_diffusers_nvfp4/ -name '*.safetensors' ! -path '*/.cache/*' | wc -l"

# All pip packages
ssh jianliu@10.10.70.88 "source ~/.bashrc && /data/venvs/vllm-ds4/bin/pip list 2>/dev/null | grep -iE 'sglang|tensorrt|torch|transformers'"

# Wan2.2 benchmark test dirs
ssh jianliu@10.10.70.88 "ls -lt /home/jianliu/work/bench_test/wan_2_2_nvfp4/"
```

## Wan2.2-T2V-A14B on RTX 5090 32GB — CUDA OOM

Wan2.2-T2V-A14B at full precision loads ~29.6 GiB on a 32 GB RTX 5090, leaving virtually no headroom for inference. Symptom: `torch.OutOfMemoryError` during model loading, process dies with `Rank 0 scheduler is dead`.

**Memory-reduction flags for SGLang diffusion serving:**
- `--dit-cpu-offload` — offload diffusion transformer layers to CPU
- `--vae-cpu-offload` — move VAE off GPU during denoising
- `--text-encoder-cpu-offload` — move text encoder off GPU
- `--dit-layerwise-offload` — layer-by-layer CPU offload for transformer
- `--mem-fraction-static 0.88` — limit GPU memory fraction

**Backend test workflow:** Benchmark test dirs in `~/work/bench_test/wan_2_2_nvfp4/` follow naming patterns:
- `wan22_nvfp4_backend_test_<timestamp>` — full backend comparison (cudnn + cutlass)
- `wan22_nvfp4_official_cudnn_cfg_sp<N>_<timestamp>` — cuDNN only, sequence parallel degree N
- `wan22_nvfp4_official_cudnn_sp<N>_<timestamp>` — cuDNN only, simpler config

## Qwen3.6-35B-A3B-FP8 Serving

**Model paths:**
- Original: `/data/models/Qwen3.6-35B-A3B`
- FP8 quantized: `/data/models/Qwen3.6-35B-A3B-FP8`

**Startup scripts (tgu01-pro-model-deployment repo):**
- Qwen3.6: `/home/jianliu/work/tgu01-pro-model-deployment/qwen_3_6/start_qwen36.sh` (DP=8, EP enabled, FP8 model)
- DeepSeek V4 Flash: `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh` (TP=8, EP, FP8 KV)

**Legacy paths (bench_test repo, still valid):**
- Qwen3.6: `/home/jianliu/work/bench_test/qwen_3_6/start_qwen36.sh`, `start_qwen36_1node.sh`
- DeepSeek V4 Flash: `/home/jianliu/work/bench_test/deepseekv4_flash/start_dsv4_flash_1node.sh`

Both repos exist on 70.88. Use the tgu01-pro-model-deployment scripts as the canonical source.

**Standard start pattern (all single-node vLLM servers):**
```bash
# SSH + source bashrc + background nohup — ALWAYS times out in-terminal but process starts fine
ssh jianliu@10.10.70.88 "source ~/.bashrc && bash <script_path> > <log_path> 2>&1 &"

# ALWAYS verify separately — do NOT rely on SSH exit code or output
ssh jianliu@10.10.70.88 "ps aux | grep 'vllm serve' | grep -v grep"
```

**Port conflict:** Both Qwen3.6 and DeepSeek V4 Flash default to port 8000. Only one can run at a time. If port is occupied, stop the old server first (`kill -9 <pid>`), wait 5s, verify it's dead with `ps`, then start the new one. SIGTERM is often insufficient — use `kill -9`.

**Known issue:** The script uses `--data-parallel-size 8` (DP=8), not TP8+EP single-node. Each rank gets TP=1. For TP8+EP single-node, a new script would need `--tensor-parallel-size 8 --enable-expert-parallel` replacing DP flags.

**Log:** `/data/vllm_qwen36_tgu.log` (tgu01 scripts), `/data/vllm_dsv4_flash_1node.log` (DeepSeek)

**Health check:**
```bash
ssh jianliu@10.10.70.88 "curl -s http://localhost:8000/v1/models 2>&1 | head -3"
```

**Benchmark script:** `test_qwen_throughput_cache.py` in `~/work/bandwidth_test/scripts/`

## Docker-Based vLLM Serving on 70.88

A Docker container runs vLLM on 70.88 (separate from the bare-metal venv serving). Check with `docker ps | grep vllm` and `docker inspect`.

**Current Docker setup (as of 2026-06-21):**
- Image: `vllm/vllm-openai:nightly` (20.4GB, installed via deb packages from aliyun mirror)
- Model: `/data/models/Qwen3.6-35B-A3B-NVFP4` mounted as `/model` (read-only)
- Command: `vllm serve /model --tensor-parallel-size 2 --trust-remote-code --quantization modelopt --kv-cache-dtype fp8 --moe-backend marlin --load-format fastsafetensors --gpu-memory-utilization 0.80 --max-num-batched-tokens 8192 --enable-chunked-prefill --language-model-only --reasoning-parser qwen3 --tool-call-parser qwen3_xml --enable-auto-tool-choice --compilation-config {"cudagraph_mode":"FULL_AND_PIECEWISE"}`
- Served model name: `/model` (use `MODEL=/model` and `SERVED_MODEL_NAME=/model` in bench scripts)
- Port: 8000

**Docker bench caveat**: The served model name is the container path (`/model`), not the host path. Bench scripts need `MODEL=/model` and `SERVED_MODEL_NAME=/model`. Tokenizer should point to the host path (`TOKENIZER=/data/...NVFP4`) for local token counting.

## Generic vLLM Bench Serve Script

**Location**: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/`
- `run_vllm_bench_serve.sh` — Bash wrapper that sets env vars and calls `test_vllm_bench_serve.py`
- `test_vllm_bench_serve.py` — Python driver that iterates over cache hit rates, builds `vllm bench serve` commands, runs them sequentially, and prints a summary table

**Key env vars**: `MODEL`, `TOKENIZER`, `TOKENIZER_MODE`, `SERVED_MODEL_NAME`, `CACHE_HIT_RATES`, `REQUESTS`, `CONCURRENCY`, `INPUT_TOKENS`, `OUTPUT_TOKENS`, `BACKEND`, `BASE_URL`, `WARMUPS`, `REQUEST_RATE`

**Tokenizer mode pitfall**: The script defaults to `TOKENIZER_MODE=deepseek_v4`. For Qwen models, set `TOKENIZER_MODE=` (empty, uses default/auto). DeepSeek models need `deepseek_v4`.

**Cache hit rate pitfall**: With very low request counts (e.g., 20), all requests fit in a single batch and the prefix cache doesn't warm up — throughput and latency are nearly identical across 0%, 40%, 80% cache hit rates. Use at least 100–200 requests to observe meaningful cache effects.

**Results dir**: `vllm_bench_results/<timestamp>/` under the script directory. Contains per-run JSON files and a `benchmark_summary.json`.

## Benchmark Directories on 70.88

All model benchmark dirs live under `/home/jianliu/work/bench_test/`; serving scripts live under `/home/jianliu/work/tgu01-pro-model-deployment/`:

| Dir | Model | Scripts |
|-----|-------|---------|
| `deepseekv4_flash/` | DeepSeek V4 Flash | `start_dsv4_flash_1node.sh` (bench_test), tgu01 canonical at `tgu01-pro-model-deployment/deepseekv4_flash/` |
| `qwen_3_6/` | Qwen3.6-35B-A3B-FP8 | `start_qwen36.sh` (DP=8), `start_qwen36_1node.sh` (TP8+EP) in bench_test; canonical DP=8 at `tgu01-pro-model-deployment/qwen_3_6/` |
| `minimax_m2_7/` | MiniMax M2.7-NVFP4 | `start_minimax_m2_nvfp4_tpep.sh` (copied from 70.95) |
| `wan_2_2_nvfp4/` | Wan2.2-T2V-A14B | `generate`, `test_*` scripts |
| `qwen_image_2512/` | Qwen2.5-VL image | `test_qwen_image_benchmark.py`, `qwen_image_multigpu_server.py` |

### Standardized Bench Script (run_vllm_bench_serve.sh)

Located at: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh`

This wrapper invokes `test_vllm_bench_serve.py` which calls `vllm bench serve` with proper flag mapping. Key env vars:

| Env Var | Default | Description |
|---------|---------|-------------|
| `MODEL` | `/home/jianliu/work/models/deepseekv4_flash` | Local tokenizer path (also used as --model) |
| `TOKENIZER` | Same as MODEL | Tokenizer path for bench tool |
| `TOKENIZER_MODE` | `deepseek_v4` | **Must override for non-DeepSeek models** (use `auto` for Qwen) |
| `SERVED_MODEL_NAME` | (none) | Override model ID sent to API (needed for Docker-served models) |
| `REQUESTS` | 200 | Number of benchmark requests |
| `CONCURRENCY` | 64 | Max concurrent requests (set to 1 for single-batch/latency tests) |
| `INPUT_TOKENS` | 2048 | Input token length |
| `OUTPUT_TOKENS` | 500 | Output token length |
| `CACHE_HIT_RATES` | `0,0.4,0.8` | Comma-separated cache hit rates to test |
| `BACKEND` | `openai` | vLLM bench backend (use `openai` for /v1/completions) |
| `BASE_URL` | `http://127.0.0.1:8000` | Server endpoint |
| `MODEL_LABEL` | Model path basename | Label for result files |
| `WARMUPS` | 1 | Warmup requests before measurement |

**Pitfall**: The default `TOKENIZER_MODE=deepseek_v4` is wrong for Qwen models. Set `TOKENIZER_MODE=` (empty) or `TOKENIZER_MODE=auto` for non-DeepSeek models.

**Pitfall**: SSH env var escaping — the Hermes terminal tool sanitizes certain strings in SSH commands (paths, numbers get replaced with `***`). Use base64 encoding or write a remote script file instead:
```bash
# Write script on remote host, then execute
ssh host 'python3 -c "
import base64; open(\"/tmp/bench.sh\",\"w\").write(base64.b64decode(\"ENCODED_SCRIPT\").decode())
" && chmod +x /tmp/bench.sh && bash /tmp/bench.sh'
```

Results go to: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/vllm_bench_results/<timestamp>/`

## DeepSeek V4 Flash Throughput Benchmark Results (2026-06-10)

Test: 200 requests, 2048 in / 500 out, concurrency 64, DeepSeek V4 Flash single-node TP=8.

| Cache hit | Success | Wall time | Throughput | p50 | p99 |
|-----------|---------|-----------|------------|-----|-----|
| 0% | 200/200 | 250.3s | 2118 tok/s | 75.2s | 96.7s |
| 40% | 200/200 | 220.5s | 2393 tok/s | 64.1s | 98.4s |
| 80% | 200/200 | 149.0s | 3500 tok/s | 47.9s | 59.1s |

Cache hit rate cuts latency ~36% and boosts throughput 65% at 80% vs 0%.
**80% cache run times out at 600s** when run inside a 3-way loop. Run 80% separately with `timeout=900`.

See `references/deepseekv4_flash_benchmark_20260610.md`.

## FP8 + TP + EP Block-k Alignment (Critical)

When running **FP8 quantized MoE models** (e.g. Qwen3.6-35B-A3B-FP8) with **TP=8 + EP enabled** on single-node, all workers fail with:

```
ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128.
```

**Root cause**: EP shards experts across GPUs, then TP further shards each expert's weight matrix. When `input_size_per_partition` (expert hidden dim after EP sharding) is 64 and `block_k=128`, the 64-dim partition cannot be subdivided into 128-element FP8 blocks.

**Workarounds** (pick one):
1. **Disable `--enable-ep-weight-filter`** — may still fail on single-node TP8+EP+FP8 due to block_k inherent to the quantization
2. **Use TP8 without EP** — `vllm serve ... --tensor-parallel-size 8 --enable-expert-parallel` (no EP, no weight filter)
3. **Use BF16 model** — non-quantized model (e.g. `Qwen3.6-35B-A3B`) has no block_k constraint, EP works fine
4. **Use DP=8 instead of TP8+EP** — the original `start_vllm_qwen.sh` uses DP=8 with TP=1 per rank; EP shards experts across DP ranks, no TP sharding conflict. Works but different parallelism profile.

**For single-node TP8+EP serving with FP8, EP must be disabled.** Single-node DP (where each rank has full TP) is the only config that works with FP8+EP.

## Qwen3.6-35B-A3B Serving (70.88)

**Model paths**:
- FP8: `/data/models/Qwen3.6-35B-A3B-FP8`
- BF16: `/data/models/Qwen3.6-35B-A3B`
- NVFP4: `/data/models/Qwen3.6-35B-A3B-NVFP4` (22GB, also on 70.98)

**Startup scripts**: `/home/jianliu/work/tgu01-pro-model-deployment/qwen_3_6/`
- `start_qwen36.sh` — DP=8, FP8 model
- `start_qwen36_nvfp4.sh` — NVFP4 model (script has `CUDA_VISIBLE_DEVICES=0` + DP=8, needs manual override for different GPU configs)

**NVFP4 on RTX 5090 (32GB) — OOM with TP=2**: Requires TP=4 minimum. Model is 22GB on disk but ~30.4 GiB/GPU with TP=2 due to activation workspace + CUDA graph + KV cache. See `mlops/vllm-tuning` skill `references/nvfp4-memory-analysis.md` for full breakdown.

**FLASHINFER_DISABLE_VERSION_CHECK**: Must be exported in the parent shell BEFORE vllm launch — worker subprocesses spawned by `multiprocessing.get_context("spawn")` may not inherit env vars set inside the bash script. Use:
```bash
source /data/venvs/vllm-ds4/bin/activate
export FLASHINFER_DISABLE_VERSION_CHECK=1
CUDA_VISIBLE_DEVICES=0,1,2,3 nohup vllm serve ... > /tmp/log 2>&1 &
```

**Known issues**:
- `FLASHINFER_DISABLE_VERSION_CHECK=1` required for all vLLM serving on this server
- `--enable-ep-weight-filter` causes `ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128` with FP8 + TP8 + EP

## DeepSeek V4 Flash — Single Node TP8

**Benchmark dir (legacy):** `/home/jianliu/work/bench_test/deepseekv4_flash/`
**Startup script (canonical):** `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`

- `start_dsv4_flash_1node.sh` — TP8, EP, 0.92 mem util, FP8 KV cache
- `test_deepseekv4_throughput_cache.py` — throughput benchmark
- `run_benchmark.sh` — wrapper (note: `test_deepseekv4_throughput_cache.py` appends `/v1/chat/completions` to base-url, so pass base-url as `http://localhost:8000` NOT `http://localhost:8000/v1/completions`)

**Benchmark results** (2048 in / 500 out, concurrency 64, 200 requests):
| Cache | Throughput | p50 | p99 |
|-------|-----------|-----|-----|
| 0% | 2118 tok/s | 75.2s | 96.7s |
| 40% | 2393 tok/s | 64.1s | 98.4s |
| 80% | 3500 tok/s | 47.9s | 59.1s |

## References

- `references/benchmark-dirs.md` — all benchmark dirs on 70.88, throughput test conventions, copy patterns
- `references/tp8_ep_fp8_blockk.md` — TP8+EP+FP8 block_k=128 alignment failure: root cause, config matrix, workarounds
- `references/wan22_nvfp4_20260609.md` — Wan2.2 OOM analysis, generate.log error chain, benchmark test dir reference.
- `references/qwen36_serving_20260611.md` — Qwen3.6-35B-A3B-FP8 serving setup, model paths, DP=8 config notes.
- **Use Tsinghua Tuna mirror**: `-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30` — faster and more reliable than default PyPI on this server.
- **SGLang transformers conflict**: SGLang 0.5.12 requires `transformers==5.6.0`. If 5.8.0 is installed, downgrade: `pip install 'transformers==5.6.0'`.
- **TRTLLM SM 9.0**: RTX 5090 SM 9.0 may not have pre-built TRTLLM wheels for CUDA 13.0 — verify after install or prepare for source build.
- **wan2.2 OOM on RTX 5090 32GB**: Full-precision Wan2.2-T2V-A14B exhausts 32GB GPU memory during load (~29.6 GiB in use, ~8 MiB free). Symptoms: server starts then "Rank 0 scheduler is dead" + `EOFError`. Mitigation: try `--dit-cpu-offload`, `--vae-cpu-offload`, `--text-encoder-cpu-offload`, BF16, or SP/Ulysses parallelism. Full diagnostic in `references/wan22_generate_oom_log.md`.
- **fsspec conflict**: TRTLLM's `datasets` dep pins `fsspec<=2024.9.0`. Pin fsspec before installing TRTLLM.
- **TP8+EP+FP8 block_k alignment**: `input_size_per_partition = 64` not divisible by `block_k = 128` — EP shards experts, TP further shards weights, creating 64-dim partitions incompatible with FP8's 128-block_k. This affects all FP8 MoE models (Qwen3.6-35B-A3B-FP8) on single-node TP8+EP. Workarounds: (1) TP8 without EP, (2) DP=8 with TP=1 per rank (original `start_qwen36.sh` approach), (3) use BF16 model.
- **flash_attn.ops missing → rotary patch**: `flash-attn-4` (CUTE template engine) is installed but lacks compiled CUDA kernels. `flash_attn.ops` import fails. The vllm-ds4-sm120 fork has its own `vllm_flash_attn.ops.triton.rotary`. Patched `rotary_embedding/common.py` to fall back. **Patch file**: `/data/vllm-ds4-sm120/vllm/model_executor/layers/rotary_embedding/common.py`. If re-installing vllm-sm120, re-apply: change `find_spec("flash_attn") is not None` check to also verify `find_spec("flash_attn.ops") is not None`, fall back to `vllm.vllm_flash_attn.ops.triton.rotary`.
- **`flash_attn.ops` missing → rotary patch**: `flash-attn-4` (CUTE template engine) is installed but lacks compiled CUDA kernels. `flash_attn.ops` import fails. The vllm-ds4-sm120 fork has its own `vllm_flash_attn.ops.triton.rotary` as fallback. Patch `vllm/model_executor/layers/rotary_embedding/common.py` line ~136: change `if find_spec("flash_attn") is not None:` to also check `find_spec("flash_attn.ops")`. Pattern:
  ```python
  if find_spec("flash_attn") is not None and find_spec("flash_attn.ops") is not None:
      from flash_attn.ops.triton.rotary import rotary_embedding_part
  elif find_spec("vllm_flash_attn") is not None:
      from vllm_flash_attn.ops.triton.rotary import rotary_embedding_part
  ```
- **`FLASHINFER_DISABLE_VERSION_CHECK=1`**: flashinfer-jit-cache version mismatch — bypass with env var.
- **Background pip**: For large installs (TRTLLM), run in background with `nohup` to avoid SSH timeout: `ssh ... "source ~/.bashrc && nohup pip install ... > /tmp/install.log 2>&1 &"`
- **RTX 5090 32GB OOM with Wan2.2-T2V-A14B**: The 14B diffusion model (~9.3 GB per transformer shard × 2) exhausts the 32GB GPU. At `performance_mode=speed`, GPU memory hits 29.55/31.36 GiB with only 8.88 MiB free, causing `torch.OutOfMemoryError` during transformer loading. Mitigations: `--vae-cpu-offload`, `--text-encoder-cpu-offload`, `--dit-cpu-offload`, or reduce latent resolution.
- **Two SGLang venvs**: Scripts using SGLang Wan (`generate.py`) use `/data/venvs/sglang-wan-nvfp4/`, not `/data/venvs/vllm-ds4/`. Check which venv a script uses before installing packages.
- **vLLM benchmark base-url double-path**: `test_deepseekv4_throughput_cache.py` and similar scripts always append `/v1/chat/completions` to `base_url` internally. Passing `http://localhost:8000/v1/completions` as `--base-url` results in `HTTP 404` (requests go to `.../v1/completions/v1/chat/completions`). Always use `http://localhost:8000` as `--base-url`. See `references/deepseekv4_flash_benchmark_20260610.md` for correct command.
- **Two script repos on 70.88**: `/home/jianliu/work/tgu01-pro-model-deployment/` (canonical) and `/home/jianliu/work/bench_test/` (legacy). Canonical path takes precedence. Both exist — disambiguation is done by task type: tgu01 = serving scripts, bench_test = benchmark/throughput scripts.
- **Qwen3.6-35B-A3B-NVFP4 Docker benchmark (2026-06-21)**: 20 requests showed NO cache hit rate effect — throughput flat across 0/40/80%. Use ≥100 requests for meaningful cache results. See `references/qwen36_nvfp4_benchmark_20260621.md`.
- **80% cache benchmark timeout**: The `test_deepseekv4_throughput_cache.py` script with `--cache-hit-rate 0.8` can exceed the default 600s script-level timeout even though vLLM completes successfully. Run the 80% test separately with `timeout=900` or higher, or increase the script's `--request-timeout` argument.