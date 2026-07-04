# DeepSeek V4 Flash — Benchmark Results (2026-06-10)

## Setup

- Server: 10.10.70.88 (8× RTX 5090 32GB, single-node, TP=8, EP enabled)
- Model: `/home/jianliu/work/models/deepseekv4_flash`
- Launch script: `/data/venvs/vllm-ds4/start_dsv4_flash_1node.sh`
- Log: `/data/vllm_dsv4_flash_1node.log`
- Test script: `test_deepseekv4_throughput_cache.py` (from `~/work/bandwidth_test/scripts/`)
- Benchmark dir: `/home/jianliu/work/bench_test/deepseekv4_flash/`
- GPU memory used at load: 19.79 GiB

## Results

200 requests, 2048 input tokens, 500 output tokens, concurrency 64.

| Cache hit | Success | Wall time | Throughput | p50 latency | p99 latency |
|-----------|---------|-----------|------------|-------------|-------------|
| 0%   | 200/200 | 250.3s | 2118 tok/s | 75.2s | 96.7s |
| 40%  | 200/200 | 220.5s | 2393 tok/s | 64.1s | 98.4s |
| 80%  | 200/200 | 149.0s | 3500 tok/s | 47.9s | 59.1s |

80% cache: **+65% throughput** vs 0%, **-36% p50 latency**.

## Bug Found and Fixed: base-url double-path

`test_deepseekv4_throughput_cache.py` always appends `/v1/chat/completions` to `base_url`.
Passing `http://localhost:8000/v1/completions` as `--base-url` → requests go to `.../v1/completions/v1/chat/completions` → HTTP 404 on all requests.

**Correct:** `--base-url http://localhost:8000` (no `/v1/completions` suffix).

## Bug Found: 80% cache run timeout

Running all 3 tests (0%, 40%, 80%) in a shell loop with combined timeout 600s → 80% run times out.
The vLLM server completes successfully, but the Python script exceeds the script-level timeout while gathering results.

**Fix:** Run 80% cache test separately with higher timeout:
```bash
ssh jianliu@10.10.70.88 "source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate && \
  python /home/jianliu/work/bench_test/deepseekv4_flash/test_deepseekv4_throughput_cache.py \
    --base-url http://localhost:8000 \
    --model /home/jianliu/work/models/deepseekv4_flash \
    --requests 200 --concurrency 64 \
    --input-tokens 2048 --output-tokens 500 \
    --cache-hit-rate 0.8 \
    --save-json /home/jianliu/work/bench_test/deepseekv4_flash/results/dsv4_flash_c0p8.json"
```

## Correct benchmark command

```bash
ssh jianliu@10.10.70.88 "source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate && \
  TS=\$(date +%Y%m%d_%H%M%S) && mkdir -p /home/jianliu/work/bench_test/deepseekv4_flash/results && \
  for RATE in 0.0 0.4 0.8; do
    python /home/jianliu/work/bench_test/deepseekv4_flash/test_deepseekv4_throughput_cache.py \
      --base-url http://localhost:8000 \
      --model /home/jianliu/work/models/deepseekv4_flash \
      --requests 200 --concurrency 64 \
      --input-tokens 2048 --output-tokens 500 \
      --cache-hit-rate \$RATE \
      --save-json /home/jianliu/work/bench_test/deepseekv4_flash/results/dsv4_flash_\${RATE}_\${TS}.json
  done"
```

## Startup issues encountered

1. `FLASHINFER_DISABLE_VERSION_CHECK=1` needed (flashinfer-jit-cache 0.6.8 vs flashinfer 0.6.11 mismatch)
2. `ModuleNotFoundError: No module named 'flash_attn.ops'` → patched `rotary_embedding/common.py` to fall back to `vllm.vllm_flash_attn.ops.triton.rotary`
3. KV cache 0.03 GiB available, needed 0.9 GiB → `--gpu-memory-utilization` raised from 0.88 to 0.92