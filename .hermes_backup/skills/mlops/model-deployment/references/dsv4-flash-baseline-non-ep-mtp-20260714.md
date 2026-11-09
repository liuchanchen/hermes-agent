# DeepSeek-V4-Flash Baseline Benchmark (70.88, Non-EP/Non-MTP)

**Date:** 2026-07-14
**Server:** 10.10.70.88 (8× RTX 5090 32GB)
**Config:** TP=8, max-model-len=262144, gpu-memory-utilization=0.9735, FP8 KV cache
- No EP, No MTP, No `--enable-expert-parallel`, No `--speculative-config`
- Tokenizer mode: `deepseek_v4`
- Compilation: `FULL_AND_PIECEWISE` with custom_ops=all
- Script: `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`
- Benchmark: `run_vllm_bench_serve.sh` defaults (200 reqs, conc=64, rate=inf, 2048 in / 500 out)
- Result dir: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/vllm_bench_results/20260714_161501/`

## Summary

| Cache | Shared | Unique | req/s | out tok/s | total tok/s | Mean TTFT | Mean TPOT | P50 TPOT |
|-------|--------|--------|-------|-----------|-------------|-----------|-----------|----------|
| 0%    | 0      | 2048   | 0.96  | 480.6     | 2,449.2     | **13.69s**| **98.6ms**| 104.2ms |
| 40%   | 819    | 1229   | 1.17  | 584.6     | 2,979.2     | **6.35s** | **91.2ms**| 93.1ms  |
| 80%   | 1638   | 410    | 1.53  | 763.7     | 3,892.0     | **3.23s** | **71.6ms**| 74.3ms  |

## Comparison: Non-MTP (this run) vs MTP2 (previous run)

Prior benchmark at max-len=422656 with `--enable-expert-parallel`, `--enable-ep-weight-filter`, and MTP2 speculative decoding:

| Metric | Non-MTP (262144) | MTP2+EP (422656) |
|--------|------------------|-------------------|
| 0% Req/s | 0.96 | 0.78 |
| 0% Mean TPOT | 98.6ms | 108.1ms |
| 0% Mean TTFT | 13.69s | 22.72s |
| 80% Req/s | 1.53 | 1.22 |
| 80% Mean TPOT | 71.6ms | 91.0ms |
| 80% Mean TTFT | 3.23s | 3.56s |

This baseline (shorter context, no MTP) is ~23% faster on request throughput and ~10% faster on TPOT. The comparison is not apples-to-apples (different max-model-len affects KV cache pressure), but establishes the non-MTP baseline for when MTP is not needed.

## Detail: TTFT by Percentile

| Cache | Mean | P50 | P90 | P95 | P99 |
|-------|------|-----|-----|-----|-----|
| 0%    | 13,685ms | 6,103ms | 34,453ms | 36,663ms | 70,171ms |
| 40%   | 6,351ms  | 3,721ms | 17,130ms | 21,453ms | 27,074ms |
| 80%   | 3,233ms  | 1,996ms | 7,698ms  | 9,524ms  | 11,106ms |

Prefix cache dramatically reduces TTFT (−54% at 40%, −76% at 80%).

## Detail: TPOT by Percentile

| Cache | Mean | P50 | P90 | P95 | P99 |
|-------|------|-----|-----|-----|-----|
| 0%    | 98.6ms  | 104.2ms | 119.6ms | 124.3ms | 128.8ms |
| 40%   | 91.2ms  | 93.1ms  | 108.4ms | 108.9ms | 110.0ms |
| 80%   | 71.6ms  | 74.3ms  | 77.7ms  | 78.3ms  | 80.7ms  |

TPOT P50-P99 spread is very tight (~25ms), indicating consistent decode performance.

## Detail: ITL by Percentile

| Cache | Mean | P50 | P90 | P95 | P99 |
|-------|------|-----|-----|-----|-----|
| 0%    | 98.6ms  | 61.6ms  | 113.1ms | 403.0ms | 620.9ms |
| 40%   | 91.2ms  | 61.4ms  | 67.5ms  | 407.6ms | 659.8ms |
| 80%   | 71.6ms  | 60.0ms  | 64.3ms  | 66.3ms  | 627.4ms |

ITL P50~60ms (decode speed). High P95/P99 indicates occasional scheduling jitter from large concurrent prefills.

## GPU Memory

All 8 GPUs: 31,202 MiB / 32,607 MiB used after server start (~95.7% utilization).
