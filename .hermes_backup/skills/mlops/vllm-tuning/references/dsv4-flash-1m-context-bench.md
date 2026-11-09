# DeepSeek-V4-Flash 1M vs 16K Context Benchmark Comparison

**Date**: 2026-06-23
**Server**: 70.98 (8× RTX PRO 6000 Blackwell 98GB)
**vLLM**: 0.1.dev1+gb709b75b4 (ds4-sm120 branch)
**Config**: TP=8, EP enabled, kv-cache-dtype=fp8, block-size=256, cudagraph_mode=FULL_AND_PIECEWISE

## Test Configuration
- Input tokens: 2048, Output tokens: 500
- Requests: 200, Concurrency: 64, request-rate=inf
- Benchmark: vllm bench serve via run_vllm_bench_serve.sh

## 16K Context (max-model-len=16384) Results

| Cache Hit | req/s | out tok/s | total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | P90 TTFT | P99 TTFT | P90 TPOT | P99 TPOT |
|-----------|-------|-----------|-------------|----------------|----------------|----------|----------|----------|----------|
| 0% | 1.29 | 646 | 3,293 | 9,454 | 76.1 | 22,624 | 31,861 | 86.2 | 92.5 |
| 40% | 1.61 | 805 | 4,102 | 8,031 | 59.2 | 14,685 | 20,378 | 70.2 | 74.1 |
| 80% | 2.04 | 1,019 | 5,195 | 6,380 | 45.8 | 9,393 | 12,202 | 53.4 | 58.0 |

## 1M Context (max-model-len=1048576) Results

| Cache Hit | req/s | out tok/s | total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | P90 TTFT | P99 TTFT | P90 TPOT | P99 TPOT |
|-----------|-------|-----------|-------------|----------------|----------------|----------|----------|----------|----------|
| 0% | 0.62 | 309 | 1,576 | 12,263 | 171.6 | 30,102 | 42,307 | 186.9 | 194.5 |
| 40% | 0.70 | 351 | 1,790 | 9,986 | 151.3 | 20,572 | 28,464 | 165.2 | 170.3 |
| 80% | 0.82 | 407 | 2,076 | 8,141 | 129.8 | 12,119 | 15,568 | 141.0 | 147.6 |

## Key Comparisons

### 1M vs 16K (same hardware, 70.98 Blackwell)

| Cache Hit | Metric | 16K | 1M | Change |
|-----------|--------|-----|-----|--------|
| 0% | out tok/s | 646 | 309 | **-52%** |
| 0% | TTFT (ms) | 9,454 | 12,263 | +30% |
| 0% | TPOT (ms) | 76.1 | 171.6 | **+126%** |
| 40% | out tok/s | 805 | 351 | **-56%** |
| 40% | TPOT (ms) | 59.2 | 151.3 | **+155%** |
| 80% | out tok/s | 1,019 | 407 | **-60%** |
| 80% | TPOT (ms) | 45.8 | 129.8 | **+183%** |

### 70.92 (RTX 5090) vs 70.98 (Blackwell), both 16K

| Cache Hit | Metric | 70.92 | 70.98 | Delta |
|-----------|--------|-------|-------|-------|
| 0% | out tok/s | 570 | 646 | +13% |
| 0% | TTFT (ms) | 15,961 | 9,454 | -41% |
| 0% | TPOT (ms) | 76.2 | 76.1 | ~same |
| 40% | out tok/s | 655 | 805 | +23% |
| 40% | TPOT (ms) | 73.2 | 59.2 | -19% |
| 80% | out tok/s | 976 | 1,019 | +4% |
| 80% | TPOT (ms) | 54.1 | 45.8 | -15% |

## Analysis

1. **1M context is devastating for concurrent throughput**: TPOT more than doubles at all cache rates because KV cache pre-allocation at 1M context consumes massive GPU memory (~89.8 GB/card), leaving far less room for concurrent batch scheduling.

2. **Blackwell advantage at 16K**: The RTX PRO 6000's 98GB HBM provides 13-23% better throughput at low cache hit rates and up to 41% better TTFT vs RTX 5090 32GB.

3. **TPOT parity at 0% cache**: At 0% cache with 16K, both GPUs show ~76ms TPOT, suggesting the decode compute is comparable and the Blackwell advantage comes from larger memory allowing better batch scheduling.

4. **Recommendation**: Use 16K context for concurrent serving workloads. Reserve 1M context only for sequential long-context tasks where single-request latency matters more than throughput.
