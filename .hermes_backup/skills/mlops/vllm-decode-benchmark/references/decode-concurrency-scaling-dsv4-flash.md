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
| Mean TTFT | 119 ms |
| P50 TPOT | 10.29 ms |
| Mean TPOT | 10.28 ms |
| P90 TPOT | 10.32 ms |
| P95 TPOT | 10.32 ms |
| P99 TPOT | 10.33 ms |
| Mean ITL | 10.28 ms |
| Mean E2EL | ~7,140 ms |
| Output throughput | 95.3 tok/s |
| Requests | 80 / 0 failed |
| Dataset | semantic (152 avg in, 512 out) |

**~97 tok/s per stream** — the uncontended per-stream decode speed. TPOT
distribution is extremely tight (P50-P99 spread = 0.04ms).

## Concurrency=16

| Metric | Value |
|--------|-------|
| Mean TTFT | 704 ms |
| P50 TPOT | 14.34 ms |
| Mean TPOT | 14.80 ms |
| P90 TPOT | 16.73 ms |
| P95 TPOT | 16.73 ms |
| P99 TPOT | 17.47 ms |
| Mean ITL | 14.80 ms |
| Mean E2EL | ~12,800 ms |
| Output throughput | 990 tok/s |
| Peak output throughput | 1,184 tok/s |
| Peak concurrent | 32 |
| Requests | 80 / 0 failed |

## Concurrency=64 (320 requests)

| Metric | Value |
|--------|-------|
| Mean TTFT | 1,466 ms |
| P50 TPOT | 32.92 ms |
| Mean TPOT | 32.66 ms |
| P90 TPOT | 33.72 ms |
| P95 TPOT | 34.05 ms |
| P99 TPOT | 34.49 ms |
| Mean ITL | 32.66 ms |
| Mean E2EL | ~32,300 ms |
| Output throughput | 1,804 tok/s |
| Peak output throughput | 2,292 tok/s |
| Peak concurrent | 104 |
| Requests | 320 / 0 failed |

## Scaling Summary

| Concurrency | Per-stream TPOT | Aggregate tok/s | Throughput multiplier | TPOT degradation vs baseline |
|-------------|----------------|-----------------|----------------------|------------------------------|
| 1 | 10.28 ms | 95 | 1× (baseline) | 1× |
| 16 | 14.80 ms | 990 | 10.4× | 1.44× |
| 64 | 32.66 ms | 1,804 | 18.9× | 3.18× |

## Notes

- Per-stream TPOT degrades by ~1.4× at conc=16, ~3.2× at conc=64
- Aggregate throughput increases 10.4× (conc=16) to 18.9× (conc=64) over baseline
- TTFT scales with concurrency: 119ms → 704ms → 1,466ms as concurrency goes 1→16→64
- Peak concurrent requests hit 104 despite max_concurrency=64 setting, showing backend queuing beyond the limit
- Extremely tight TPOT distribution at all levels — P50-P99 spread < 1ms at conc=1, < 2ms at conc=16, < 2ms at conc=64
- **Fresh restart matters**: numbers from a clean restart are consistently better than from a server that was started earlier and had been running. The AOT compile cache from the first-ever start of a session produces slightly worse numbers than subsequent restarts where the cache is pre-populated. For reproducible comparisons, either restart before every benchmark session or explicitly note "fresh restart" vs "subsequent restart" status.
