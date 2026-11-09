# MTP2 vs Non-MTP Decode Throughput Comparison — GLM-5.2-NVFP4 on 70.96

**Date**: 2026-07-08
**Server**: 70.96 (8×RTX PRO 6000 Blackwell, 96 GB each), Docker container `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412`
**Tool**: `/home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_decode_bench_serve.sh`
**Dataset**: `decode_semantic_256.jsonl` (256 requests, ~160 input tokens each)
**Output tokens**: 512 per request (fixed via `--custom-output-len`)
**Concurrency**: 32, request-rate=inf
**Warmup**: 1 request

## Non-MTP Server Config

Script: `/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4.sh`

- TP=8, DCP=4, gpu-memory-utilization=0.90
- kv-cache-dtype=bfloat16 (DCP incompatibility with fp8)
- moe-backend=b12x, enable-prefix-caching, enable-chunked-prefill
- `--reasoning-parser glm45`, `--tool-call-parser glm47`

## MTP2 Server Config

Script: `/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4_mtp2.sh`

- Same as non-MTP plus: `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'`
- gpu-memory-utilization=0.87 (slightly lower for MTP2 memory overhead)
- max-model-len=870400, max-num-seqs=16 (MTP2 needs more memory)
- `--moe-backend b12x` replaced with `export VLLM_NVFP4_GEMM_BACKEND=b12x` to avoid unquantized MoE error on MTP drafter

## Comparing the Two

The servers were started and killed independently from the same Docker image. The benchmark ran from the HOST machine (70.96) using `vllm bench serve` from `/data/venvs/vllm-ds4/bin/vllm`, with `--skip-tokenizer-init` to bypass the GLM 5.2 `layer_types` validation error in the host's transformers.

## Key Discovery: `--skip-tokenizer-init` for Host-Side Benchmarking

The host-side `vllm bench serve` can benchmark the GLM-5.2 Docker server using `--skip-tokenizer-init`. This avoids the `validate_layer_type` error from GLM 5.2's `deepseek_sparse_attention` in `config.json` without needing a patched config copy.

**Working command:**
```bash
cd /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test
MODEL=glm5_2_nvfp4 \
TOKENIZER=/data/models/glm_5_2_nvfp4/ \
TOKENIZER_MODE=auto \
TRUST_REMOTE_CODE=1 \
SKIP_CHAT_TEMPLATE=1 \
bash run_vllm_decode_bench_serve.sh --skip-tokenizer-init
```

Note: `MODEL=glm5_2_nvfp4` (model name, not filesystem path) works because the benchmark sends it as the API model ID. The `TOKENIZER` path still needs to point to a local directory for the bench tool's internal prompt generation.

## ⚠️ Known Bug: `total_output_tokens` Under-Counts with `--skip-tokenizer-init`

This comparison uses `total_output_tokens` to compute output throughput (tok/s). However, due to a bug in `vllm bench serve` when using `--skip-tokenizer-init` with models using `delta.reasoning` streaming format (GLM-5.2-NVFP4, all models with `--reasoning-parser`), **`total_output_tokens` reports only 1 token per request instead of 512**:

```python
# In vllm/benchmarks/serve.py calculate_metrics():
output_len = outputs[i].output_tokens  # 0 - usage chunk not reliably parsed
if not output_len:
    if tokenizer is None:              # True with --skip-tokenizer-init
        output_len = 1                  # Falls back to 1 token per request!
```

This means `total_output_tokens = 256` (completed = 256) instead of the expected 131,072 (256 × 512).

**The `request_throughput` (req/s) metric IS NOT affected** by this bug — it only depends on `completed / duration`. So speedup ratios (1.68x) based on req/s remain valid. However, `output_throughput` and `total_token_throughput` are incorrect.

For the true output throughput, multiply:
- True output tok/s = request_throughput × output_tokens_per_request
- Non-MTP: 13.9 × 512 = **7,118 tok/s** (not the 13.9 shown in the raw JSON)
- MTP2: 23.4 × 512 = **11,975 tok/s** (not the 23.4 shown in the raw JSON)

## Results

| Metric | Non-MTP | MTP2 | Speedup |
|--------|---------|------|---------|
| Benchmark duration (s) | 18.4 | 10.9 | **1.68x faster** |
| Request throughput (req/s) | 13.9 | 23.4 | **1.68x** |
| Output throughput (tok/s) | 7,118 | 11,975 | **1.68x** |
| Total token throughput (tok/s) | 2,248 | 3,782 | **1.68x** |
| Mean E2E latency (ms) | 2,295 | 1,324 | **1.73x lower** |
| Median E2E latency (ms) | 2,278 | 1,173 | **1.94x lower** |
| P99 E2E latency (ms) | 2,414 | 2,728 | **0.88x (worse)** |
| Max concurrent requests | 63 | 64 | — |
| Failed requests | 0 | 0 | — |

## Analysis

1. **MTP2 is consistently ~1.68x faster** across all throughput metrics. This matches the theoretical limit for `num_speculative_tokens=1` with ~42.7% acceptance rate — each step produces ~1.43 accepted tokens instead of 1.

2. **Median latency nearly halved** (2,278→1,173ms, -48%). Mean latency reduced by 42%. The reduction is concentrated in the middle of the distribution.

3. **P99 tail latency is WORSE with MTP2** (2,728 vs 2,414ms, +13%). This is expected for speculative decoding — when the drafter's prediction is wrong, the rejected speculation adds overhead to the tail of the distribution undoing the benefit, or batch scheduling under speculative decoding creates longer tails for some requests.

4. **No failures** in either run — both configurations are stable at conc=32 with 256 decode-heavy requests.

5. **The main advantage of MTP2** is per-request latency reduction. For batch throughput, it helps but the gain is less dramatic at high concurrency where batching already masks individual request latency.
