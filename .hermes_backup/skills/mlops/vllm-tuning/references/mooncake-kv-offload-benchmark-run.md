# Mooncake KV-offload Benchmark Protocol & Full-Run Analysis

Session 2026-08-20/21 on 70.88. Two artifacts analyzed: the executable benchmark
protocol `mooncake_kv_offload/tests/test_design.txt` and the run result
`.../tests/results/20260820-full-v1/REPORT.md` (+ `analysis.json`).

## K = startup-reported GPU KV token capacity

The single most important definition in the protocol (line 153): **"Let K be the
startup-reported GPU KV token capacity."** It is parsed from the vLLM startup log
line `GPU KV cache size: K tokens` (line 124), NOT computed by hand. All workload
sizing is derived from K:
- W1 (HBM-fit control): working set ≤ 0.5 × K → tests zero-overhead, expect
  local GPU hit ≥ 95%, external load ≈ 0.
- W2a/W2b (DRAM/recompute): working set ≥ 2 × K → forces GPU eviction so
  Mooncake DRAM restores actually happen.
- SSD sizing: measure `vllm:mooncake_store_operation_bytes_total{operation="save_put"}`
  aggregate delta across TP ranks for a 32K prefix → B32K; then
  `bytes_per_prefix(P) = B32K * P / 32768` and `Nssd(P) = ceil(2 * D / bytes_per_prefix(P))`.
  If the counter is unavailable/zero the run FAILS rather than estimating.

**Memory semantics:** the full K-token KV pool is RESERVED (cudaMalloc'd) at engine
init — `nvidia-smi` shows the memory consumed immediately even though
`kv_cache_usage_perc` is 0. The pool is fixed at K; it never grows past K. So
"allocated" at init = yes (full K), "used" = grows 0→K as prefixes cache.

## Experiment design (from test_design.txt)

System: single-node vLLM, DeepSeek-V4-Flash-0731, image
`vllm/vllm-openai:v0.25.0-flashinfer0614-local`, Mooncake 0.3.10, 8× RTX 5090
TP=8, fp8 MLA KV, block-size 256, loopback TCP. Fixed: `--enable-prefix-caching`,
`--kv-cache-memory-bytes 2147483648` (2 GiB/GPU — deliberately small so eviction is
reproducible), `--max-model-len 73728`, `--enable-expert-parallel`.

Configs:
- A baseline = vLLM + APC, no Mooncake (launched via `baseline` action in
  `enable_mooncake_kv_offload.sh` — removes only MooncakeStore).
- B dram = A + connector, `GLOBAL_SEGMENT_SIZE=64GB`, `OFFLOAD_ON_EVICT=false`
  (no disk persistence — keeps tier unambiguous).
- C ssd = A + connector, `GLOBAL_SEGMENT_SIZE=16GB`, `OFFLOAD_ON_EVICT=true`,
  `EVICTION_HIGH_WATERMARK=0.70`, `EVICTION_RATIO=0.20`, `USE_URING=false`,
  `OFFLOAD_TOTAL_LIMIT=1099511627776`. **io_uring is blocked on this host**
  (`Operation not permitted`) — image's fallback could WRITE SSD buckets but
  returned `RPC_FAIL` on reads, hence USE_URING=false recorded as part of the
  SSD result.

Workload matrix: W0 cold-miss/save overhead (8K prefix, conc 1+16),
W1 HBM-fit control, W2a DRAM prefix-length sweep (2K/8K/32K/64K),
W2b DRAM concurrency sweep (1/4/16/32/64), W3a/W3b SSD equivalents,
W4 mixed agent-like (128 reusable prefixes, Zipf exponent 1.2, 1000 req/conc).
All requests: token-ID prompts, `[exact P-token prefix] + [unique 128-token suffix]`
+ output; P is a multiple of 256; fill/replay share prefix token IDs with different
suffixes; unique first-256-token block per prefix keeps hashes independent.

## 20260820-full-v1 gate results (REPORT.md)

| Gate | Result |
|---|---|
| DRAM tier ≥95% pure | PASS (16/16, fraction 1.000, 0 failed keys) |
| SSD tier ≥95% pure | PASS (16/16, fraction 1.000, 0 failed keys) |
| W0 throughput loss <5% | PASS |
| W1 TTFT/throughput regression <5% | PASS |
| DRAM/SSD break-even evaluated | PASS |
| canonical artifact sets complete | PASS |
| all full profiles present | FAIL |
| zero request errors | FAIL (14; all SSD: `BatchRequestError` TimeoutError) |
| zero Mooncake failed keys | FAIL (all SSD) |
| zero paired output mismatches | FAIL (3726 / 10575 = 35%) |
| W1 local hit ≥95% | FAIL |
| **overall** | **FAIL** |

### Headline numbers
- Break-even prefix length: **DRAM 8192, SSD 8192** tokens (below 8K restore is
  SLOWER than recompute: DRAM 2K ratio 1.043, SSD 2K ratio 1.116).
- Best DRAM restore speedup: 4.0× @ 65K prefix (ratio 0.248); 3.3× @ 32K; 2.0× @ 8K.
- Best SSD restore speedup: 3.6× @ 65K (ratio 0.277); 3.0× @ 32K; 1.9× @ 8K.
- W4 mixed Zipf (agent-like): DRAM up to **6.4×** (conc=4), SSD up to 5.3× (conc=16).
- Concurrency sweet spot for DRAM 8K: conc=4 → 3.07× speedup (best of the sweep).

### Why the run FAILED (capacity + determinism)
1. **SSD pool overflow**: SSD pool grew to 2.3 TiB, `/data` hit 100%, invalidating
   SSD W4 C=64. Design note (lines 402-407): failed-capacity result, NOT valid SSD
   C=64 performance. Failed-key counters concentrated in SSD W3/W4 (worst 8075 in
   `zipf1.2_c4 measured`, 5469 in c64).
2. **35% output mismatch across ALL configs — including baseline**: this is a
   determinism issue in the stack (async scheduling / chunked prefill / CUDAGraph
   FULL_AND_PIECEWISE are not bit-reproducible under concurrency), not a Mooncake
   failure. The protocol requires byte-identical outputs for paired requests but
   vLLM 0.25 with these flags doesn't guarantee it. Investigate determinism before
   trusting any correctness gate.

## Key takeaways for future runs
- **Check the target already has the image** (registry-prefixed tag, identical ID)
  before any save/transfer — 70.98 already had this exact image as
  `10.10.91.56/sw2/vllm/vllm-openai:v0.25.0-flashinfer0614-local`; a retag replaced
  a planned 8.8 GB transfer (see `docker-image-transfer-retag-supervisor-restart.md`).
- SSD sizing MUST respect the 1.2× `OFFLOAD_TOTAL_LIMIT` free-space requirement
  before a profile starts; the 20260820 run's failure was predictable from the
  design doc.
- `docker stop` alone does NOT stop a bench-driven vLLM — the supervisor harness
  (`run_..._validation_v16.sh`, `tee`, `tail -f`) auto-restarts the container.
  Kill the harness PIDs too, and check `docker inspect ... .State.StartedAt` to see
  if a "stopped" container came back.
- Report parsing pattern: gates + failed_key_phases + request_errors +
  terminal_failures + comparisons are all top-level keys in `analysis.json`;
  `comparisons[i]` has `ttft_ratio_other_over_baseline`, `ttft_ratio_ci95`,
  `ttft_speedup_baseline_over_other`, `throughput_ratio_other_over_baseline`,
  `output_mismatch_rate`.
