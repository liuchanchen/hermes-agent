# GLM-5.1-NVFP4 Benchmark Script Fixes (2026-06-08)

## Script
`/home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh`

## What Was Wrong

### `openai-chat` backend rejects `/v1/completions`
The server has `--reasoning-parser glm45` active. The `openai-chat` backend prepends the GLM chat template and routing layer, which does not support the raw completions endpoint — requests hang or return errors. **Fix:** `--backend openai` (raw OpenAI backend, bypasses chat template).

### Warmup request deadlocks the server
`--num-warmups 1` (the default in many templates) sends one warmup request before the benchmark. Under load testing with high concurrency, this can deadlock the vLLM engine — GPU stays at ~97% utilization but no requests are served, and the warmup response never returns. **Fix:** `--num-warmups 0`.

### HF network calls from WSL
The tokenizer download was attempted from the local machine (no network to HuggingFace from WSL). **Fix:** Use the local model path `--tokenizer /data/models/glm_5_1_nvfp4/` + `HF_HUB_OFFLINE=1` env var.

### No debug output when things go wrong
The original script did not capture detailed per-request logs. **Fix:** `--save-detailed` saves a `.log` alongside the JSON result for post-hoc analysis.

## Current Working Command Block

```bash
cmd="source ~/.bashrc && \
export HF_HUB_OFFLINE=1 && \
source /data/venvs/vllm-ds4/bin/activate && \
$VLLM_BENCH \
    --backend openai \
    --base-url '$BASE_URL' \
    --model '$MODEL' \
    --tokenizer /data/models/glm_5_1_nvfp4/ \
    --tokenizer-mode slow \
    --endpoint /v1/completions \
    --seed 42 \
    --num-prompts '$NUM_PROMPTS' \
    --num-warmups 0 \
    --random-input-len '$INPUT_LEN' \
    --random-output-len '$OUTPUT_LEN' \
    --random-prefix-len '$prefix_len' \
    --random-range-ratio '$RANDOM_RANGE' \
    --max-concurrency '$CONCURRENCY' \
    --save-result \
    --result-dir '$RESULT_DIR' \
    --result-filename 'glm5n_2048in_512out_${cache_pct}_${TIMESTAMP}.json' \
    --save-detailed \
    --disable-tqdm \
"
```

## Pre-Benchmark Checklist

**Before running the benchmark script, verify the server is healthy:**

```bash
# 1. API layer alive? (not sufficient alone)
curl -s http://10.10.70.96:8000/v1/models

# 2. Engine alive? (REQUIRED — do NOT skip this)
timeout 30 curl -s -X POST http://10.10.70.96:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
# If timeout → engine deadlocked, restart server first
```

**If engine is deadlocked:** Kill all vLLM processes, clear Triton cache, restart via `/data/model_startup_script/start_glm5_nvfp4_docker.sh`. See `SKILL.md` Section 5 (Pre-Startup Cleanup) for full procedure.

## Run Commands

```bash
# Standard run (3 scenarios: 0%, 40%, 80% cache hit rate)
bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh

# Quick smoke test
NUM_PROMPTS=20 bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh

# Custom rate (default: burst all at once = inf)
RATE=8 bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh
```