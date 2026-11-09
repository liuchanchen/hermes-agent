# MooncakeStore AgentX A/B Test (DeepSeek V4 Flash TP4, 2026-08-26, 70.107)

Complete A/B methodology using **AgentX via AIPerf** (not vllm bench serve / prefix_repetition).
Confirms and extends `mooncake-kv-offload-worse-when-low-reuse.md` and
`mooncake-kv-offload-tp4-clean.md`: in real agentic traffic with high local prefix
hit-rate, Mooncake does **write-only tax with zero external reuse**.

## Key finding (the whole point)

Across every tested config (Phase-0 smoke c2; Phase-1 full-AgentX c8 at 8 GiB and 12 GiB
KV budgets; Phase-2 T3 paired c8@12G), Mooncake did large `save_put` (hundreds of MB
offloaded to the store) but **`lookup_exists_total_bytes` / GET bytes stayed 0** — the
store was a write sink. Local AgentX prefix-cache hit was already ~96%, so the KV blocks
evicted to Mooncake were "dead" (never re-requested); every active prefix was satisfied
from GPU cache.

**Gating rule (carry this forward): do NOT interpret a Mooncake run's latency/throughput
as an external-reuse result unless GET bytes / confirmed L3 hit counts are NONZERO.**
A run with PUT-only is measuring connector tax, nothing else.

## Why the vLLM `--kv-transfer-config` MooncakeStoreConnector never read back

- `offload_on_evict=1` writes evicted blocks, but the connector's read path never fired
  because nothing that got evicted was needed again (local APC covered the working set).
- Confirms the older finding: "write-only tax — 111,504 lookups, 16,204 save_put /
  15.69 GiB, ZERO load_get ops, external hit rate 0.0%".

## Deployment commands (fathomless serving image)

Script: `tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_pro6_fix6_mooncake_kv_offload.sh`
subcommands: `start` (Mooncake) | `baseline` (plain APC) | `stop|status|logs|check`.

```bash
# baseline arm — SAME kv-cache-memory-bytes as mooncake arm
GPUS=0,1,2,3 TP=4 MAX_MODEL_LEN=1048576 NAME=my-baseline \
  bash start_..._mooncake_kv_offload.sh baseline --kv-cache-memory-bytes 12884901888

# mooncake arm — unique CACHE_PREFIX per measured run (avoid store contamination)
GPUS=0,1,2,3 TP=4 MAX_MODEL_LEN=1048576 NAME=my-mooncake \
  MOONCAKE_RUNTIME_DIR=/home/jianliu/mooncake-runtime \
  MOONCAKE_POOL_DIR=/home/jianliu/mooncake-pool CACHE_PREFIX=agentx-run-001 \
  bash start_..._mooncake_kv_offload.sh start --kv-cache-memory-bytes 12884901888
```

`TP` defaults to 8 — **always set `GPUS` and `TP` together** (TP4 = GPU 0-3).
`--kv-cache-memory-bytes` takes bytes (12 GiB = 12884901888). Keep identical across arms.

## Mooncake runtime extraction (serving image lacks mooncake binaries)

fathomless image has the connector but NOT `mooncake_master/client/store.so`. Extract
from a vLLM image that ships them, tar, stream to target, point `MOONCAKE_RUNTIME_DIR`:

```bash
docker run --rm -v /tmp/mooncake-runtime:/out --entrypoint bash \
  vllm/vllm-openai:v0.25.0-flashinfer0614-local -c \
  'cp -a /usr/local/lib/python3.12/dist-packages/mooncake \
        /usr/local/lib/python3.12/dist-packages/mooncake_transfer_engine.libs \
        /usr/local/lib/python3.12/dist-packages/mooncake_transfer_engine-*.dist-info /out/'
tar czf /tmp/mooncake-runtime.tar.gz -C /tmp/mooncake-runtime .
cat /tmp/mooncake-runtime.tar.gz | ssh <target> 'cat > /tmp/mr.tgz && mkdir -p ~/mooncake-runtime && tar xzf /tmp/mr.tgz -C ~/mooncake-runtime'
```

## Cold-start cost per arm switch

Each vLLM start recompiles mHC/TileLang kernels + FlashInfer autotune + CUDA graph
capture: **~15-18 min** (TP4, 1M context) before the 900s AIPerf run. Plan each arm
switch as ~20 min overhead. FlashInfer autotune cache (`/cache/vllm/flashinfer_autotune_cache/`)
helps on repeat starts.

## AIPerf AgentX command (per arm)

```bash
export PATH=/home/jianliu/aiperf-env/bin:$PATH
export AIPERF_DATASET_CONFIGURATION_TIMEOUT=1800 AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT=1800
aiperf profile --scenario inferencex-agentx-mvp \
  --url http://127.0.0.1:8000 --model DeepSeek-V4-Flash \
  --tokenizer /modelzoo/deepseekv4-flash-0731 --endpoint-type chat \
  --public-dataset semianalysis_cc_traces_weka_062126 \
  --concurrency 8 --benchmark-duration 900 --random-seed 20260826 \
  --use-server-token-count --artifact-dir /home/jianliu/work/abtest/<cell>-<arm>-<seed>
```

## Quantified results (all `submission_valid: true`)

T3 (c8, 12 GiB, seed 20260826, 89 requests both arms — near-perfect pair: same 89 reqs,
same 88,476 output tokens, only 50 input tokens diff):

| metric | baseline | mooncake | Δ |
|---|---|---|---|
| TTFT avg | 2927 ms | 2969 ms | +1.45% |
| TTFT p50 | 1111 ms | 1318 ms | +18.65% |
| TTFT p90 | 7357 ms | 5647 ms | −23.24% |
| ITL avg | 11.76 ms | 13.17 ms | +12.02% |
| ITL p95 | 15.72 ms | 19.03 ms | +21.06% |
| Req Lat p50 | 8557 ms | 8635 ms | +0.91% |
| Output tok/s | 94.12 | 94.12 | ~0% |
| Mooncake KV | — | PUT ~400 MB, GET 0 bytes | — |

Calibration 8G vs 12G: throughput scale factor 1.0000× despite +50% KV capacity
(TTFT avg −12%, ITL p95 +27% — no clean scaling, heavy-tailed noise at 72 samples).

## Statistical analysis workflow (Codex CLI) — use this, it catches what naive reads miss

Codex (codex-cli 0.147.0, `codex exec`, needs a git repo) gives a rigorous second opinion
on A/B JSONs. Setup: copy each `profile_export_aiperf.json` into a git dir, then
`codex exec "<analysis prompt>"`.

Insights it surfaced that a naive comparison missed:
- **p50-vs-avg divergence = tail-outlier mechanism, not uniform shift.** T3 TTFT p50
  +18.65% but avg +1.45% because p90 improved −23% (distribution shape changed). ITL avg
  +12% was driven by ONE severe outlier (max 137.5 ms vs 28 ms, +390%).
- **Statistical caveats are real**: 1 run per condition → the experimental unit is the
  run, not the request; 57-89 reqs means p95 is 3-5 slowest requests and p99 ≈ max;
  closed-loop scheduling makes observations endogenous. Naive 95% CI for T3 TTFT:
  +42 ms ± 1160 ms → not significant.
- **Throughput equality is partly mechanical** when request count/tokens/wall-interval
  match exactly — strong evidence of no GAIN, but coarse resolution.
- **Calibration insight**: quantiles non-monotonic across 8G→12G (p90 worsens 38.8%,
  p95 improves 22.8%) = a few requests moving percentile ranks, not a real scaling trend.

## How to actually trigger external reuse (if that's the goal)

1. **Shrink local KV below the prefix working set** — 8 GiB was NOT enough (still no
   external miss). Try 2-4 GiB, or raise concurrency (c16/c32) so reuse distance exceeds
   local capacity.
2. **Cross-replica (distributed-cache) test** — warm prefix A on one TP4 replica, replay
   identical A on a second replica sharing the same Mooncake store. Most promising path.
3. **Forced eviction sequence** — prefix A → enough distinct long prefixes to evict A
   locally → prefix A again (byte-identical).
4. Writer/reader must share model revision, tokenizer, TP/cache layout, KV dtype, page
   size, namespace, and Mooncake master/client config.

## Result files (70.107)

`/home/jianliu/work/abtest/` per-run dirs: `phase0-baseline|phase0-mooncake|
calib-mooncake-8g|calib-mooncake-12g|t3-baseline-s1|t3-mooncake-s1`, each with
`profile_export_aiperf.json/csv`, `profile_export.jsonl` (per-request),
`server_metrics_export.*`, `logs/`.

## Notion

A/B design + results documented on the SemiAnalysis AgentX Notion KB page
(`AgentX-MooncakeStore-A-B-Test-Design-DeepSeek-V4-Flash-TP4`, Chinese translation +
实验结果 section).
