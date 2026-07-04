# Qwen3.6-35B-A3B-NVFP4 Docker Benchmark Results (70.88)

## Server Config

- **Host**: 10.10.70.88 (Docker container)
- **Image**: `vllm/vllm-openai:nightly`
- **Model**: Qwen3.6-35B-A3B-NVFP4 (mounted read-only at `/model`)
- **GPU**: 2× RTX 5090 32GB, TP=2
- **Served model name**: `/model`
- **Quantization**: modelopt NVFP4, Marlin MoE backend, FP8 KV cache
- **gpu-memory-utilization**: 0.80
- **max-num-batched-tokens**: 8192
- **Flags**: `--enable-chunked-prefill --language-model-only --reasoning-parser qwen3 --tool-call-parser qwen3_xml --enable-auto-tool-choice`

## Benchmark: conc=64, 200 requests (2026-06-20)

Config: 2048 input / 500 output tokens, concurrency=64, request-rate=inf

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0% | 3045.0 | 15517.3 | 1,706 | 16.0 |
| 40% | 3147.8 | 16041.0 | 1,312 | 16.2 |
| 80% | 3170.6 | 16157.4 | 1,308 | 16.0 |

Results dir: `70.88:.../vllm_bench_results/20260620_*` (from earlier session)

## Benchmark: conc=1 (single-batch), 20 requests (2026-06-21)

Config: 2048 input / 500 output tokens, concurrency=1, request-rate=inf

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | Mean E2EL (ms) | Duration (s) |
|-----------|-------------|-------------|----------------|----------------|----------------|-------------|
| 0% | 261.0 | 1390.5 | 114.1 | 3.61 | 1915.2 | 38.3 |
| 40% | 259.8 | 1372.5 | 113.4 | 3.63 | 1924.0 | 38.5 |
| 80% | 261.1 | 1374.6 | 111.5 | 3.61 | 1914.7 | 38.3 |

Results dir: `70.88:.../vllm_bench_results/20260621_122441/`

### Key Finding: Single-batch shows no cache hit rate benefit

With concurrency=1, requests are processed sequentially — each request completes before the next starts. The KV cache prefix sharing doesn't help because there's no cross-request reuse. Throughput, TTFT, TPOT, and E2E latency are nearly identical across all 3 cache levels.

### Latency comparison: conc=1 vs conc=64

| Metric | conc=1 | conc=64 | Ratio |
|--------|--------|---------|-------|
| Output tok/s | ~261 | ~3045-3171 | 11.7-12.1x higher at conc=64 |
| Mean TPOT (ms) | 3.6 | 16.0 | 4.4x higher at conc=64 |
| Mean TTFT (ms) | 112-114 | 1308-1706 | 11-15x higher at conc=64 |

The 4.4x TPOT increase at conc=64 reflects batch scheduling overhead, not cache effects. Single-batch TPOT reveals true per-token decode latency.
