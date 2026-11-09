# Why enabling Mooncake KV-offload can be SLOWER — 70.96 pro6_fix6 run (2026-08-24)

Run dir: `deepseekv4_flash/vllm_bench_results/pro6_fix6_mooncake_vs_baseline_20260824_160030` on 70.96.
Launcher: `start_dsv4_flash_pro6_fix6_mooncake_kv_offload.sh`; serving image `fathomless-main-verify:gpu-smoke-fix6`.
Model `/modelzoo/deepseekv4-flash-0731/`, TP=8, `lucifer-cutlass`, standard-mtp0, FP8 KV, prefix caching.
Workload: 200 req, concurrency 64, 2048 in / 500 out, request-rate inf, temperature 0, shared-prefix rates 0%/40%/80%.

## Results

| Shared prefix | Baseline req/s | Mooncake req/s | Change | Mean TPOT |
|---|---:|---:|---:|---:|
| 0%  | 3.111 | 2.252 | -27.6% | 33.7 -> 48.2ms (+43%) |
| 40% | 3.748 | 2.049 | -45.3% | 27.8 -> 55.0ms (+98%) |
| 80% | 2.812 | 3.365 | +19.7% | 37.7 -> 30.7ms (-19%) |

Key pattern: higher shared-prefix rate -> Mooncake wins more. This is NOT "SSD offload is slow";
it is "at low reuse the connector pays the write tax with zero read benefit".

## Root cause chain (verified from logs, not guessed)

1. **Write-only tax at low reuse (core cause).**
   - Report: 111,504 external-store key lookups (0 failed), 16,204 key writes = 16,846,974,720 bytes (15.69 GiB), 0 failed writes.
   - BUT: `load_get` ops = 0 and periodic vLLM logs show `External prefix cache hit rate: 0.0%` the whole run.
   - GPU KV usage stayed 2-5%, so Automatic Prefix Caching hit inside the GPU; external storage was never read.
   - Every prompt's KV is async `save_put` into the store; with no reuse there is pure write, no read.

2. **save_put spikes stall decode.**
   - Logged `save_put_avg_ms` peaks: 813.9ms (cold), 138.9ms, 72.1ms / 71.8ms (periodic).
   - Mooncake ITL std explodes: baseline ~40ms -> Mooncake 318-521ms (0%/40%).
   - TPOT roughly doubles (up to +98%) — write path contends with EngineCore/decode.

3. **io_uring degraded path (environment).**
   - Client log: `[SharedUringRing] io_uring_queue_init failed: Operation not permitted`;
     `I/O will use regular (non-fixed-buffer) io_uring, which is correct but slightly less optimal`.
   - Same signature as the 70.88 run — container env lacks fixed-buffer io_uring.

4. **expandable_segments disabled for Mooncake.**
   - Mooncake needs stable registered KV addresses; launcher clears `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
     only for Mooncake runs (baseline keeps it). Worse allocator profile.

## Why 80% won — and why it is NOT an offload proof

At 80% shared prefix, APC prefill savings (GPU-internal) outweigh the write tax.
External hit rate was STILL 0.0% and load_get was still 0 — the win came from a
cache-friendly workload, not from SSD-offload capability. The report itself states:
"did not record external-store load operations ... should not be interpreted as a
direct SSD-offload performance measurement."

## How to actually measure offload value

The standard 0/40/80 prefix bench never forces the external LOAD path. To trigger it:
- Shrink GPU KV (small `--kv-cache-memory-bytes`, e.g. 2 GiB/GPU) so APC cannot hold the working set
  (this is what the 70.88 `test_design.txt` protocol does: W2 working set >= 2*K).
- Fill past the DRAM high-watermark (0.90) so SSD eviction/restore actually happens, then replay evicted prefixes.
- Watch `load_get` counters and tier purity (memory-loaded/disk-loaded >= 0.95, failed keys = 0).
- Watch for capacity safety: keep free disk >= 1.2x OFFLOAD_TOTAL_LIMIT (70.88 full-v1 hit /data at 100% with a 2.3 TiB SSD pool).

## Metrics to read when analyzing Mooncake runs

- vLLM periodic log: `GPU KV cache usage: X%`, `Prefix cache hit rate: X%`, `External prefix cache hit rate: X%`.
- `KV Transfer metrics:` line: `lookup_exists_* / save_exists_* / save_put_* / load_get_*` with avg/p90 ms, keys, bytes, failed_keys.
- Mooncake master log: `Master service started ... enable_offload=1, offload_on_evict=1, eviction_high_watermark_ratio=0.9`.
- Mooncake client log: look for `io_uring_queue_init failed` / `Bucket backend max_total_size not set`.
- Raw benchmark JSON: `ttfts`, `itls`, `mean_tpot_ms`, `std_itl_ms`, `duration`, `request_throughput`.
