# Qwen3.6-35B-A3B-NVFP4 vLLM Bench Serve — 2026-06-21

## Setup

- **Server**: 70.88 (oem88), RTX 5090 32GB × 8
- **Serving**: Docker container `vllm/vllm-openai:nightly`, TP=2
- **Model**: Qwen3.6-35B-A3B-NVFP4 (mounted as `/model`)
- **Quantization**: modelopt NVFP4, kv-cache fp8, moe-backend marlin
- **GPU mem util**: 0.80, chunked-prefill enabled, max-batched-tokens 8192
- **Script**: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh`
- **Backend**: openai (`/v1/completions`)

## Results (20 requests, 2048 in / 500 out, concurrency 64)

| Cache Hit Rate | Shared | Unique | Done | req/s  | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | Duration (s) |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **0%**  | 0    | 2048 | 20/20 | 3.533 | 1766.6 | 9411.4 | 795.2 | 9.71 | 5.66 |
| **40%** | 819  | 1229 | 20/20 | 3.491 | 1745.3 | 9220.6 | 786.8 | 9.87 | 5.73 |
| **80%** | 1638 | 410  | 20/20 | 3.507 | 1753.5 | 9232.8 | 819.5 | 9.75 | 5.70 |

## Percentile Latency (ms)

| Metric | 0% cache | 40% cache | 80% cache |
|:-:|:-:|:-:|:-:|
| p50 TTFT | 805.6 | 797.4 | 830.5 |
| p90 TTFT | 1248.3 | 1241.0 | 1271.4 |
| p99 TTFT | 1264.9 | 1242.2 | 1272.6 |
| p50 TPOT | 9.69 | 9.85 | 9.73 |
| p99 TPOT | 10.91 | 11.07 | 10.95 |
| p50 E2EL | 5641.4 | 5712.6 | 5686.8 |

## Key Finding

**No cache hit rate effect observed** at 20 requests. All three runs produced nearly identical throughput (~3.5 req/s, ~1750 out tok/s) and latency (~800ms TTFT, ~9.7ms TPOT). With only 20 requests, all requests dispatch in a single batch — the prefix cache doesn't warm up across requests. Compare with DeepSeek V4 Flash results (200 requests) where 80% cache hit gave 65% throughput boost.

**Recommendation**: Use ≥100 requests (ideally 200) to see cache effects. The `vllm bench serve` `--random-prefix-len` simulates shared prefix across requests, but the benefit only manifests when requests are spread over time and the KV cache accumulates.

## Command Used

```bash
ssh jianliu@10.10.70.88 'source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate && \
  cd ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test && \
  MODEL=/model \
  TOKENIZER=***  CACHE_HIT_RATES=0,0.4,0.8 \
  REQUESTS=20 \
  CONCURRENCY=64 \
  INPUT_TOKENS=*** \
  OUTPUT_TOKENS=*** \
  BACKEND=openai \
  BASE_URL=http://127.0.0.1:8000 \
  bash run_vllm_bench_serve.sh 2>&1'
```

Results dir: `vllm_bench_results/20260621_121618/`
