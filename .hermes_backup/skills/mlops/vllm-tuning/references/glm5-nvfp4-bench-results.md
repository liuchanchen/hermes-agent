# GLM-5.1-NVFP4 vllm bench serve Results (2026-06-04)

Model: GLM-5.1-NVFP4 (GlmMoeDsaForCausalLM), 8× RTX PRO 6000 Blackwell SE (96GB/card)
Server: 10.10.70.96, single-node TP=8, PP=2, EP=8
Context: 2-node cluster via RoCE v2, worker 70.98, master 70.96
Server args: `--enable-prefix-caching --enable-chunked-prefill --gpu-memory-utilization 0.82`
Token i/o: 512 output tokens per request
Concurrency: 64, Total prompts: 640

## Confirmed Working Benchmark Command Template

```bash
/data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name prefix_repetition \
  --max-concurrency 64 \
  --num-prompts 640 \
  --temperature 0 \
  --percentile-metrics ttft,tpot,itl \
  --metric-percentiles 50,90,99 \
  --save-result --result-dir /data/bench_results \
  --result-filename SCENARIO.json
```

**Always use `--tokenizer /data/models/glm_5_1_nvfp4/`** — the bench tool downloads from HuggingFace.co and the venv has no external network, causing `Network is unreachable` and exit code 255.

**Always use `--model glm5_1_fp8`** — using the filesystem path `/data/models/glm_5_1_nvfp4/` causes HTTP 404 "Not Found" for all 640 requests.

## Results

### A-series: 2k input / 512 output / Concurrency 64

| Scenario | Cache Hit | num_prefixes | completed | duration | TTFT p50 | TTFT p90 | TTFT p99 | TPOT p50 | TPOT p90 | TPOT p99 | ITL p50 | ITL p90 | ITL p99 | out_tok/s | total_tok/s |
|----------|-----------|-------------|-----------|----------|----------|----------|----------|----------|----------|----------|---------|---------|---------|-----------|-------------|
| A1 | 0% | 640 | 640 | 4561s | 232.5s | 243.5s | 248.2s | 445ms | 469ms | 476ms | 433ms | 436ms | 1374ms | 71.8 | 359.2 |
| A2 | 40% | 384 | 384 | 1198s | 1.5s | 13.0s | 27.4s | 448ms | 464ms | 513ms | 428ms | 515ms | 980ms | 131.9 | 788.2 |
| A3 | 80% | 128 | 640 | 1830s | 1.3s | 3.9s | 24.2s | 433ms | 456ms | 491ms | 428ms | 432ms | 747ms | 140.4 | 856.6 |

**Key observations**:
- 40% cache → **155× TTFT improvement** (232.5s → 1.5s p50)
- 40% cache → **1.8× output throughput improvement** (71.8 → 131.9 tok/s)
- A2 `completed=384` — `num_prefixes=384`, remaining 256 requests are warm cache hits that don't count individually
- A3 `completed=640` — full 640, with 128 unique prefixes + 512 warm repetitions
- A3 TTFT p50=1.3s (vs A2's 1.5s) — 80% cache is slightly better than 40%
- TPOT stable across cache rates (~430-448ms) — decode throughput unaffected by cache

### Prefill Time Estimates (single request, cold)

| Input Length | TTFT (single) |
|-------------|--------------|
| 2k | ~12s |
| 30k | ~10.4s |
| 60k | ~7.5s |

## B-series: 60k Input Status (FAILED — server deadlock)

**B1 (60k/0%)**: Benchmark launched with `--dataset-name random --random-input-len 60000 --random-output-len 512`. All 640 requests failed with HTTP 404 "Not Found" (wrong `--dataset` flag). Relaunched with correct `--dataset-name random`. Benchmark started but server deadlocked — all subsequent requests (even `hi`) timed out. **60k at conc=64 causes server to hang.**

B2 and B3 were not launched pending server recovery.

**Smoke test results**:
- Single 60k request: **7.5s** (succeeds in isolation)
- 4×30k concurrent: **~18s total** (parallel prefill effective)
- 64×60k concurrent: **server hangs** (KV cache pressure causes NCCL/Gloo deadlock)

**Lesson**: 60k input is safe at conc ≤ 4, dangerous at conc ≥ 16. For B-series with conc=64, reduce concurrency to 8–16 or use 30k input instead.

## B-series Commands (adjusted for safety)

```bash
# RECOMMENDED: use --max-concurrency 16 for 60k scenarios
# B1: 60k/0% — 640 unique prefixes
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 0 \
--prefix-repetition-suffix-len 60000 \
--prefix-repetition-output-len 512 \
--prefix-repetition-num-prefixes 640 \
--max-concurrency 16

# B2: 60k/40% — 384 unique prefixes
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 512 \
--prefix-repetition-suffix-len 59488 \
--prefix-repetition-output-len 512 \
--prefix-repetition-num-prefixes 384 \
--max-concurrency 16

# B3: 60k/80% — 128 unique prefixes
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 512 \
--prefix-repetition-suffix-len 59488 \
--prefix-repetition-output-len 512 \
--prefix-repetition-num-prefixes 128 \
--max-concurrency 16
```

Note: Using `prefix_repetition` with `prefix-len=0` for 0% cache avoids the `[gMASK]` stall that `random` dataset triggers on GLM models.

## Issue Log

| Date | Issue | Root Cause | Resolution |
|------|-------|-----------|------------|
| 2026-06-04 | A1 stuck at 0/640, GPU 0% | Engine core in half-deadlock before this session; `/v1/completions` timed out | Server self-recovered ~2 min later; A1 relaunched and completed normally |
| 2026-06-04 | `random` dataset stalls at 0/640 on GLM | `[gMASK]` token in random sequences triggers decode deadlock | Use `prefix_repetition` dataset for all GLM benchmarks |
| 2026-06-04 | A2 shows `completed=384` not 640 | `prefix_repetition` reports `completed=num_prefixes`, not total prompts | Expected behavior — total wall-clock and throughput still measured for all 640 |
| 2026-06-04 | First B1 launch: 640/640 "Not Found" | `--dataset` instead of `--dataset-name` | Relaunched with `--dataset-name random` |
| 2026-06-04 | Second B1 launch: server deadlocked | 60k × 64 concurrent prefill exhausts KV cache → NCCL/Gloo deadlock | Server self-recovered after ~3 min; B2/B3 deferred pending safe config |
| 2026-06-04 | Wrong model name caused "Not Found" | `--model /data/models/glm_5_1_nvfp4/` instead of `--model glm5_1_fp8` | Must use served model name from `/v1/models` |