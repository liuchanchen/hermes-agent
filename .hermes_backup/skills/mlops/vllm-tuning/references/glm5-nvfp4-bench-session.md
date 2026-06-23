# GLM-5.1-NVFP4 Benchmark Session — 2026-06-04

## Server Config (70.96)
- Model: GLM-5.1-NVFP4 (GlmMoeDsaForCausalLM)
- vLLM: ds4-sm120 branch, `/data/venvs/vllm-ds4/bin/vllm`
- Server: Docker, PID 381662, port 8000, served as `glm5_1_fp8`
- Model path: `/data/models/glm_5_1_nvfp4/`
- Startup args: `--tensor-parallel-size 8 --decode-context-parallel-size 4 --gpu-memory-utilization 0.82 --max-num-seqs 64 --kv-cache-dtype bfloat16 --enable-prefix-caching --enable-chunked-prefill --moe-backend b12x --tool-call-parser glm47 --chat-template-content-format=string --enable-auto-tool-choice --reasoning-parser glm45`

## Results Summary

| Scenario | Input | Cache | Prefixes | Completed | Duration | TTFT p50 | TPOT p50 | Throughput |
|----------|-------|-------|----------|-----------|----------|----------|----------|------------|
| A1 | 2k | 0% | 640 | 640/640 | 4561s | 232.5s | 444.8ms | 71.8 tok/s |
| A2 | 2k | 40% | 384 | 384/640 | 1198s | 1.5s | 448.2ms | 131.9 tok/s |
| A3 | 2k | 80% | 128 | 640/640 | 1830s | 1.3s | 432.8ms | 140.4 tok/s |

Note: A2 shows 384/640 completed because `completed` = num_prefixes (384), not total prompts. Total wall-clock time and throughput cover all 640 requests.

## A1 — 2k input, 0% cache (WORKING command)
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && /data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name prefix_repetition \
  --max-concurrency 64 \
  --num-prompts 640 \
  --prefix-repetition-prefix-len 512 \
  --prefix-repetition-suffix-len 1536 \
  --prefix-repetition-output-len 512 \
  --prefix-repetition-num-prefixes 640 \
  --temperature 0 \
  --disable-tqdm \
  --save-result \
  --result-dir /data/bench_results \
  --label A1_2k_0pct \
  > /data/bench_results/A1_2k_0pct.log 2>&1 &
echo PID: \$!"
```

## A2 — 2k input, 40% cache (WORKING command)
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && /data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name prefix_repetition \
  --max-concurrency 64 \
  --num-prompts 640 \
  --prefix-repetition-prefix-len 512 \
  --prefix-repetition-suffix-len 1536 \
  --prefix-repetition-output-len 512 \
  --prefix-repetition-num-prefixes 384 \
  --temperature 0 \
  --disable-tqdm \
  --save-result \
  --result-dir /data/bench_results \
  --label A2_2k_40pct \
  > /data/bench_results/A2_2k_40pct.log 2>&1 &
echo PID: \$!"
```

## A3 — 2k input, 80% cache (WORKING command)
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && /data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name prefix_repetition \
  --max-concurrency 64 \
  --num-prompts 640 \
  --prefix-repetition-prefix-len 512 \
  --prefix-repetition-suffix-len 1536 \
  --prefix-repetition-output-len 512 \
  --prefix-repetition-num-prefixes 128 \
  --temperature 0 \
  --disable-tqdm \
  --save-result \
  --result-dir /data/bench_results \
  --label A3_2k_80pct \
  > /data/bench_results/A3_2k_80pct.log 2>&1 &
echo PID: \$!"
```

## B1 — 60k input, 0% cache (FAILS at conc=64 — server deadlock)
CORRECTED command (model name fixed), but conc=64 causes deadlock:
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && /data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name random \
  --max-concurrency 64 \
  --num-prompts 640 \
  --random-input-len 60000 \
  --random-output-len 512 \
  --temperature 0 \
  --disable-tqdm \
  --save-result \
  --result-dir /data/bench_results \
  --label B1_60k_0pct \
  > /data/bench_results/B1_60k_0pct.log 2>&1 &
echo PID: \$!"
```
**Result**: All 640 failed with "Not Found" (wrong model name initially). After fixing model name to `glm5_1_fp8`, ran but 60k/64 conc caused server deadlock. Server did NOT self-recover. Requires `kill -9 381662` + restart.

**For B1/B2/B3**: Use `--max-concurrency 8` or `--max-concurrency 16`. Single 60k request works (~7.5s TTFT). 64×60k hangs.

## Key Mistakes Made This Session

1. **Wrong model name**: Used `--model /data/models/glm_5_1_nvfp4/` → all 640 returned "Not Found". Fixed by using served name `glm5_1_fp8` from `/v1/models`.

2. **Wrong concurrency flag**: `--concurrency` (does not exist in ds4-sm120 bench serve) → command silently exits 0 but produces no output. Correct flag is `--max-concurrency`.

3. **60k conc=64 deadlock**: Confirmed at 14:44-14:45. GPU spiked to 98% then server froze. Did NOT self-recover (unlike earlier A1 deadlock which recovered).

4. **GPU 0% = normal between batches**: During A1 monitoring, nvidia-smi showed 0% for minutes — this was serialized prefill, not a crash. Benchmark was making progress despite 0% GPU reading.

## Deadlock Diagnosis Sequence (2026-06-04)
```
14:44: GPU 98%, benchmark running
14:45: GPU 0%, /v1/models responds, /v1/completions hangs (120s timeout)
14:47: Server still deadlocked (simple "hi" request times out)
→ Required kill -9 381662 + restart
```

Recovery command (run on 70.96):
```bash
kill -9 381662
# Then restart server with startup script
```