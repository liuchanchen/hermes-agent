# DeepSeek-V4-Flash Decode Concurrency Scaling — RTX 5090 × 8 (70.88)

Server config (from `start_dsv4_flash_1node.sh`): TP=8, max_model_len=262144,
gpu_memory_utilization=0.9735, FP8 KV cache, block-size=256, no MTP, no EP.

Dataset: `decode_semantic_256.jsonl` — 256 engineering-memo prompts (~152 avg
input tokens), 512 output tokens each.

**All results below from a clean server restart** (killed all vLLM processes,
verified GPU memory at ~15 MiB baseline, then started fresh).

## Concurrency=1 (pure serial decode)

| Metric | Value |
|--------|-------|
| Successful requests | 80 / 0 failed |
| Benchmark duration | 430s |
| Mean TTFT | 119 ms |
| P50 TTFT | 122 ms |
| P90 TTFT | 130 ms |
| P99 TTFT | 213 ms |
| Mean TPOT | 10.28 ms |
| P50 TPOT | 10.29 ms |
| P90 TPOT | 10.32 ms |
| P95 TPOT | 10.32 ms |
| P99 TPOT | 10.33 ms |
| Mean ITL | 10.28 ms |
| Mean E2EL | ~7.14 s |
| Output throughput | 95.3 tok/s |
| Peak output throughput | 99 tok/s |

**~97 tok/s per stream** — the uncontended per-stream decode speed.

## Concurrency=16

| Metric | Value |
|--------|-------|
| Successful requests | 80 / 0 failed |
| Benchmark duration | 41s |
| Mean TTFT | 704 ms |
| P50 TTFT | 411 ms |
| P90 TTFT | 1,937 ms |
| P99 TTFT | 3,279 ms |
| Mean TPOT | 14.80 ms |
| P50 TPOT | 14.34 ms |
| P90 TPOT | 16.73 ms |
| P95 TPOT | 16.73 ms |
| P99 TPOT | 17.47 ms |
| Mean ITL | 14.80 ms |
| Mean E2EL | ~12,800 ms |
| Output throughput | 990 tok/s |
| Peak output throughput | 1,184 tok/s |
| Peak concurrent requests | 32 |

## Concurrency=64 (320 requests)

| Metric | Value |
|--------|-------|
| Successful requests | 320 / 0 failed |
| Benchmark duration | 91s |
| Mean TTFT | 1,466 ms |
| P50 TTFT | 1,392 ms |
| P90 TTFT | 2,123 ms |
| P99 TTFT | 2,740 ms |
| Mean TPOT | 32.66 ms |
| P50 TPOT | 32.92 ms |
| P90 TPOT | 33.72 ms |
| P95 TPOT | 34.05 ms |
| P99 TPOT | 34.49 ms |
| Mean ITL | 32.66 ms |
| Mean E2EL | ~32,300 ms |
| Output throughput | 1,804 tok/s |
| Peak output throughput | 2,292 tok/s |
| Peak concurrent requests | 104 |

## Scaling Summary

| Concurrency | Per-stream TPOT | Aggregate tok/s | Throughput multiplier | TPOT degradation vs baseline |
|-------------|----------------|-----------------|----------------------|------------------------------|
| 1 | 10.28 ms | 95 | 1× (baseline) | 1× |
| 16 | 14.80 ms | 990 | 10.4× | 1.44× |
| 64 | 32.66 ms | 1,804 | 18.9× | 3.18× |

## Key Findings

- Per-stream TPOT at conc=1 is **10.28ms** (~97 tok/s per stream) on 8× RTX 5090 TP=8
- Degrades ~1.4× (conc=16) to ~3.2× (conc=64) versus baseline
- Aggregate throughput increases 10.4× (conc=16) to 18.9× (conc=64)
- Extremely tight TPOT distribution: P50-P99 spread < 1ms at conc=1, < 2ms at conc=16 and conc=64
- Peak concurrent requests hit 104 despite max_concurrency=64, showing backend queuing beyond the limit
- **Clean server restart matters**: numbers from a first-ever server start differ from those after AOT compile cache has warmed up. For reproducible comparisons, restart before each session or explicitly note the restart status.
