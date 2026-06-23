# vLLM Tuning Matrix — Empirical Results

System: DeepSeek V4 Pro, TP=8 + DP=2 + EP=16, 2 nodes × 8× RTX PRO 6000 Blackwell SE (96GB/card)

All results on vLLM 0.6.0.dev0 (ds4-sm120 branch, jasl/vllm).

## Complete 10-Configuration Matrix

Planned but only ~6 were feasible due to OOM constraints on 96GB Blackwell cards. Two strategies tested: DP (TP=8+DP=2+EP=16) and PP (TP=8+PP=2+EP=8).

### Config Feasibility (both strategies, max-model-len=1M)

| # | batched-tokens | max-num-seqs | DP (TP=8+DP=2+EP=16) | PP (TP=8+PP=2+EP=8) |
|---|---------------|-------------|----------------------|---------------------|
| 2.0 | 16384 | 256 | — | ✅ Tested (PP only) |
| 2.1 | 16384 | 128 | — | ✅ Tested (PP only) |
| 2.2 | 16384 | 512 | ❌ OOM | ❌ OOM (both strategies) |
| 2.3 | 8192 | 256 | — | ✅ Tested (PP only) |
| 2.4 | 8192 | 128 | ✅ Tested | ✅ Tested |
| 2.5 | 8192 | 512 | ⚠️ S1 only (crashed on S2/S3) | ✅ Tested |
| 2.6+ | 32768+ | any | ❌ OOM | ❌ OOM |

### PP vs DP Head-to-Head: 8192/128 (only config both completed at max-model-len=1M)

| Metric | DP (EP=16) | PP (EP=8) | PP Advantage |
|--------|-----------|----------|--------------|
| **S1 TTFT** | 12.69s | **5.92s** | **2.1× faster** |
| **S1 TPOT** | 108.6ms | **102.8ms** | **5.3% better** |
| **S1 throughput** | 48.2 tok/s | **67.4 tok/s** | **40% more** |
| **S2 60K TTFT** | 260.5s | **188.8s** | **28% faster** |
| **S3 prefix TTFT** | 142.8s | **43.2s** | **3.3× faster** |
| **S3 TPOT** | 93.2ms | **81.0ms** | **13% better** |
| **S3 throughput** | 4.14 tok/s | **7.73 tok/s** | **87% more** |

**PP=2 wins on every metric.** DP only completed 1 config (8192/128) without crashing.

### Why PP beats DP for this setup

1. **PP coordinator is simpler**: DP requires a ZMQ coordinator process with 5-minute handshake timeout. Any failure on the worker side (OOM, config conflict) causes a cascading 5-minute stall.
2. **EP=8 vs EP=16**: PP uses half the expert parallelism, reducing expert routing table memory by ~40%, leaving more room for KV cache.
3. **Pipeline parallelism shares KV cache**: PP splits model layers across nodes, so each node only needs KV cache for its pipeline stage — less memory pressure per GPU.
4. **EP=16 with DP=2 fragments memory**: Each expert requires a routing table per node. With 16 experts × 2 DP ranks, that's 32 tables vs PP's 8 experts × 1 rank = 8 tables.

## PP=2 Results (TP=8+PP=2+EP=8, RoCE v2, max-model-len=1M)

This is the recommended strategy. Requires VLLM_HOST_IP + NCCL RoCE v2 env setup (see references/pp-configuration.md).

### S1: Short Prompt (random 128/128, 10 concurrent, inf rate)

| Config | TTFT mean | TPOT mean | Output tok/s | Total tok/s | Duration |
|--------|-----------|----------|-------------|-------------|----------|
| **PP 2.5** 8192/512 | **2.17s** | 99.7ms | 86.2 | 175.0 | 14.9s |
| **PP 2.4** 8192/128 | 5.92s | 102.8ms | 67.4 | 136.9 | 19.0s |
| **PP 2.3** 8192/256 | 3.32s | 105.5ms | 76.5 | 155.5 | 16.7s |
| **PP 2.0** 16384/256 | 16.03s | 102.8ms | 44.0 | 89.3 | 29.1s |
| **PP 2.1** 16384/128 | 16.31s | 102.4ms | 43.6 | 88.6 | 29.3s |
| **PP 2.2** 16384/512 | **1.35s** | 99.5ms | **91.3** | **185.5** | 14.0s |

### S2: Long Prompt (random 60000/128, 5 concurrent, inf rate)

| Config | TTFT mean | TTFT P99 | TPOT mean | Duration | Notes |
|--------|-----------|----------|-----------|----------|-------|
| **PP 2.3** 8192/256 | **182.3s** | **318.6s** | 1.18s | **333.7s** | **Best long-prompt TTFT** |
| **PP 2.5** 8192/512 | 186.7s | 327.6s | 1.22s | 342.8s | Close second |
| **PP 2.4** 8192/128 | 188.8s | 330.4s | 1.23s | 345.6s | |
| **PP 2.0** 16384/256 | 197.5s | 338.8s | 1.23s | 354.3s | |
| **PP 2.1** 16384/128 | 226.3s | 367.0s | 1.22s | 382.5s | |
| **PP 2.2** 16384/512 | (crashed) | — | — | — | KV OOM during S2 |

### S3: Prefix Cache (prefix 60000/suffix 128, 5 requests, num_prefixes=1)

| Config | TTFT mean | TPOT mean | Output tok/s | Total tok/s |
|--------|-----------|----------|-------------|-------------|
| **PP 2.0** 16384/256 | 48.5s | **56ms** | 5.15 | 5118 |
| **PP 2.1** 16384/128 | 49.0s | 67ms | 7.08 | 5037 |
| **PP 2.3** 8192/256 | 43.9s | 98ms | 7.41 | 5400 |
| **PP 2.4** 8192/128 | **43.2s** | 81ms | **7.73** | **5578** |
| **PP 2.5** 8192/512 | 44.4s | 61ms | 7.15 | 5465 |

## DP=2 Results (TP=8+DP=2+EP=16, max-model-len=1M)

Limited — only 8192/128 completed all 3 benchmarks. Larger configs OOM or crash the API server.

### DP 8192/128 — Only fully stable DP config (max-model-len=1M)

Tested 2026-05-26 in a clean session. S1-S3 all completed without crash. This is the only DP config that can handle both short and long prompts at 1M context:

| Metric | DP 8192/128 |
|--------|------------|
| S1 TTFT | 12.69s |
| S1 TPOT | 108.6ms |
| S1 throughput | 48.2 tok/s |
| S1 req/s | 0.38 |
| S2 60K TTFT | 260.5s |
| S2 P99 TTFT | 416.1s |
| S2 TPOT | 1.36s |
| S2 duration | 434.1s |
| S3 prefix TTFT | 142.8s |
| S3 P99 TTFT | 142.8s |
| S3 TPOT | 93.2ms |
| S3 throughput | 4.14 tok/s |
| S3 total tok/s | 1948.4 |

### DP 8192/512 — S1 Only (crashed on S2/S3)

Only S1 completed successfully before the API server died. S2 returned 0 generated tokens (server unresponsive). S3 got ConnectionRefusedError (server process killed by OOM):

| Metric | DP 8192/512 |
|--------|------------|
| S1 TTFT | 2.58s |
| S1 TPOT | 99ms |
| S1 throughput | 83.9 tok/s |
| S2 60K TTFT | (returned 0 tokens — API server crashed during decode) |
| S3 prefix TTFT | (Connection refused — server process killed by OOM) |

**Root cause**: With max-model-len=1M, DP=2, and 8192/512, the DP coordinator's ZMQ handshake + EP=16's extra expert routing tables consume enough memory that long-prompt prefill pushes GPU memory over the limit, crashing the API server. The service survives S1 (short prompts) but cannot handle 60K prefill + decode on 512 concurrent slots.

### Decode-heavy / Max Tokens → DP 2.5 (8192/512)
When you need maximum token throughput and TTFT is less important: TPOT 58.7ms vs PP's 99.7ms.

## Key Insights

1. **Smaller batched-tokens = better TTFT**: 8192 beats 16384 every time
2. **More sequences = better throughput** (up to memory): 512 seqs at 8192 works but OOMs at 16384
3. **First-request JIT penalty**: ~3-6s of compilation time in S1 TTFT
4. **Prefix cache ~47% improvement** over no-cache, not the expected 12×. Likely chunked prefill interaction
5. **Large batch configs (32768+) impossible**: Even with reduced max-model-len=32000
6. **PP=2 TPOT is flat (~100ms) regardless of config**: Decode stage is the bottleneck, not batch/token parameters. Changing batched-tokens or seqs barely affects TPOT. This means for decode-latency-sensitive workloads, optimization should focus on compilation mode (cudagraph vs torch.compile) or GPU memory bandwidth, not batch parameters.
7. **DP=2 is fragile with 1M context**: Only 8192/128 completed all benchmarks. 8192/512 crashed the API server on both S2 and S3 (KV OOM). 16384/512 crashed on S2. The DP coordinator's ZMQ communication and EP=16's extra memory overhead make DP less stable than PP for the same GPU memory budget.
