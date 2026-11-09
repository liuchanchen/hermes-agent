# Mooncake KV-offload TP4 clean run — compilation excluded, still slower (2026-08-24, 70.96)

Run: `deepseekv4_flash/vllm_bench_results/pro6_fix6_tp4_mooncake_vs_baseline_20260824_194038` on 70.96.
The accepted TP4 measurements contain **zero** inference-time Triton/TileLang compilation.
This is the follow-up to `mooncake-kv-offload-worse-when-low-reuse.md` (TP8 compile-contaminated run)
that isolates the real cause: **the write-only tax, not JIT compilation**.

## Result (accepted, zero-JIT)

200 req, conc 64, 2048-in/500-out, request-rate inf, temp 0, TP=4, seed 20260824, warmup seed 20260823 (disjoint).

| Shared prefix | Mooncake req/s | Baseline req/s | Delta | TTFT delta | TPOT delta |
|---|---|---:|---:|---:|---:|
| 0% | 2.794 | 2.931 | -4.69% | +8.51% | +4.93% |
| 40% | 3.307 | 3.620 | -8.64% | +17.32% | +9.47% |
| 80% | 4.242 | 4.448 | -4.62% | +10.64% | +4.20% |

Aggregate: Mooncake 600 reqs / 179.2s (3.348 req/s) vs baseline 168.5s (3.562 req/s) = **-6.00%**.
Equal-weight TTFT/TPOT/E2EL +11.8% / +6.2% / +6.8%.

## How compilation was excluded (the methodology — reuse this)

1. Disposable TP4 baseline server populated a **fresh shared compile cache**.
2. Workload repeated untimed until a full pass produced **no new JIT messages** (round 2 still had 13, round 3 had 0).
3. Each profile started fresh, ran the whole workload untimed with disjoint seed `20260823`, waited for `Running: 0` + `GPU KV usage 0.0%`.
4. Recorded a **server-log boundary line**; the timed run began only after it. The whole log after the boundary was scanned for JIT messages.
5. Gate: `compilation_checks.tsv` — mooncake_attempt1 had 2 events → rejected; attempt2 → 0 → accepted; baseline_attempt1 → 0 → accepted.

**Verification pitfall**: counting JIT lines in the log is NOT enough — check whether they fall INSIDE the measured window (after the boundary line) or in warmup. attempt2-vllm.log had 2 JIT warnings (lines 453/526, 02:23) but both were before the boundary (line 1045, 02:27:19) → warmup only, accepted.

## Root cause — write-only tax (compilation NOT the cause)

External KV reuse got zero benefit:
- All 25 external prefix-cache samples were `0.0%`.
- 606 lookup batches checked 111,504 keys but `lookup_exists_total_bytes = 0` (exists-check only, never read data).
- Mooncake master reported **0 Get operations**, 0 evictions, 0 SSD bytes — all data stayed in the 128 GB DRAM tier.
- GPU KV usage peaked at only **7.9%** — APC absorbed all repeats in-GPU, external store never hit.

Mooncake paid storage-side costs in the accepted window:
- 6,193 `save_put` batches stored 16,172 keys / **33.66 GiB**.
- Weighted save_put latency ~8.9 ms; **max avg_ms spike 567 ms**.
- Adds GPU→host copies, RPC/metadata work, host memory bandwidth, connector scheduling to the request path.

ITL/TPOT evidence of periodic stalls (not constant slowdown):
- Mooncake itl_p99 ~190-199 ms vs baseline ~152-154 ms.
- Mooncake std_itl 43.0 / 41.2 ms (0%/40%) vs baseline 39.0 / 31.8 ms.

## Secondary config differences (not the cause here)

- Mooncake must clear `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (registered/pinned KV addresses must stay stable); baseline keeps it.
- `io_uring_queue_init` not permitted → fallback to non-fixed-buffer path. Did NOT affect this run (SSD usage was 0) but must be fixed before evaluating the SSD tier.

## Why 40% is worst (-8.64%)

Baseline benefits from APC in-GPU hits (more shared prefixes than 0%), while Mooncake still pays full save_put on every request + only partially benefits → gap widens.

## How to actually measure offload value (the correct next test)

Two-phase populate/churn/replay:
1. Populate reusable prefixes.
2. Force GPU KV blocks out (shrink `--kv-cache-memory-bytes` / gpu-memory-utilization so APC can't hold the working set).
3. Replay the same prefixes → real load/Get hits.
Accept the test ONLY when logs show non-zero external hit rate + non-zero load/Get bytes. Keep the disjoint-seed warmup + zero-JIT gate.

## Caveat

Only one accepted measured pass per profile, Mooncake-then-baseline order — treat small deltas as a single-run result, not a CI.
