# GLM-5.1-NVFP4 vLLM Serve Benchmark Reference

## Context (2026-06-04)

Benchmark attempt for GLM-5.1-NVFP4 on 10.10.70.96 (8× RTX PRO 6000 Blackwell 96GB).
vLLM server was in a **deadlocked state** — `/v1/models` returned 200 OK but `/v1/completions` timed out.
All `vllm bench serve` attempts failed with exit 255 (connection refused / timeout).

**Status as of session end:** vLLM engine deadlock confirmed. Server needs full restart before benchmarking can proceed.

## vLLM bench serve Command

```bash
/data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model <served_model_name> \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name <random|prefix_repetition> \
  --max-concurrency 64 \
  --num-prompts 640 \
  --random-input-len <2048|60000> \
  --random-output-len 512 \
  --random-prefix-len 0 \
  --percentile-metrics ttft,tpot,itl \
  --metric-percentiles 50,90,99 \
  --save-result \
  --result-dir /data/bench_results \
  --result-filename <scenario>.json \
  --temperature 0 \
  2>&1 | tee /data/bench_results/<scenario>.log
```

### Critical flags
- **`--tokenizer /data/models/glm_5_1_nvfp4/`** — ALWAYS required. 70.96 has no external network (huggingface.co times out). If omitted, vLLM attempts HF download → `Network is unreachable` → exit 255.
- **`--temperature 0`** — vLLM bench no longer defaults to greedy decoding. Required for deterministic output.
- **`--save-result --result-dir --result-filename`** — saves JSON result to the specified directory.

## Test Matrix

| Scenario | Input | Cache Hit | Dataset | Command snippet |
|----------|-------|----------|---------|----------------|
| A1_2k_0pct | 2048 | 0% | `random` | `--random-input-len 2048 --random-output-len 512 --random-prefix-len 0` |
| A2_2k_40pct | 2048 | 40% | `prefix_repetition` | `--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 --prefix-repetition-output-len 512 --prefix-repetition-num-prefixes 384` |
| A3_2k_80pct | 2048 | 80% | `prefix_repetition` | same but `--prefix-repetition-num-prefixes 128` |
| B1_60k_0pct | 60000 | 0% | `random` | `--random-input-len 60000 --random-output-len 512 --random-prefix-len 0` |
| B2_60k_40pct | 60000 | 40% | `prefix_repetition` | `--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 59488 --prefix-repetition-output-len 512 --prefix-repetition-num-prefixes 384` |
| B3_60k_80pct | 60000 | 80% | `prefix_repetition` | same but `--prefix-repetition-num-prefixes 128` |

**Concurrency:** 64 (all scenarios)
**Prompts:** 640 (all scenarios)
**Output length:** 512 tokens (all scenarios)

### Cache hit rate formula
- 40% hit → 60% of requests get a prefix → `num_prefixes = 640 × 0.6 = 384`
- 80% hit → 20% of requests get a prefix → `num_prefixes = 640 × 0.2 = 128`
- Requires server started with `--enable-prefix-caching`

## Launch Pattern

Use `setsid` from SSH for background launch on server:

```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && setsid \
  /data/venvs/vllm-ds4/bin/vllm bench serve [args] \
  </dev/null >/data/bench_results/<scenario>.log 2>&1 &"
```

- `setsid` creates a new session — process survives SSH disconnection
- `</dev/null >/dev/null 2>&1` — redirect stdin/stdout/stderr to prevent SSH from blocking
- `background=true` terminal calls from agent are the reliable launch mechanism

**CAUTION:** The SSH subprocess exit code from `setsid` is NOT the benchmark exit code. The benchmark runs asynchronously on the server. Check result JSON in `/data/bench_results/` after waiting ~10-30 minutes.

## Diagnostics

### Server health (ALWAYS check before benchmarking)
```bash
# 1. API alive?
curl -s http://localhost:8000/v1/models | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"

# 2. Engine alive? (the real check — don't skip this)
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":16,"temperature":0}'

# 3. GPU status
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader

# 4. Bench processes
ps aux | grep 'vllm bench' | grep -v grep | wc -l
```

### If benchmark shows 0/N progress
- Check GPU utilization during the run — if 0%, engine is stuck
- Check `tail -10 /data/bench_results/<scenario>.log` for errors
- Most likely cause: engine is deadlocked (see Engine Health Check section of main SKILL.md)

## Result JSON Shape

```json
{
  "completed": 640,
  "failed": 0,
  "total_requests": 640,
  "mean_ttft_ms": 1234.5,
  "mean_tpot_ms": 45.2,
  "throughput_tokens_per_second": 1423.7
}
```

Percentile metrics (when `--percentile-metrics` is set):
```json
{
  "ttft_percentile_50_ms": 1100.0,
  "ttft_percentile_90_ms": 2200.0,
  "ttft_percentile_99_ms": 4500.0,
  "tpot_percentile_50_ms": 40.0,
  "tpot_percentile_90_ms": 60.0,
  "tpot_percentile_99_ms": 120.0,
  "itl_percentile_50_ms": 42.0,
  "itl_percentile_90_ms": 65.0,
  "itl_percentile_99_ms": 130.0
}
```