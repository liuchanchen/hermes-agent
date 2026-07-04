# GLM-5.1-NVFP4 Prefix Cache Benchmark

## Script

`/home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh`

Executable bash script. Runs on 70.96 via SSH (vllm bench serve only available on remote venv).

## Benchmark Matrix

| Scenario | Input | Output | Prefix len | Cache hit rate |
|----------|-------|--------|------------|----------------|
| 0% cache | 2048 | 512 | 0 | 0% |
| 40% cache | 2048 | 512 | 819 | 819/2048 ≈ 40% |
| 80% cache | 2048 | 512 | 1638 | 1638/2048 ≈ 80% |

## How `--random-prefix-len` Works

`--random-prefix-len N` adds **N fixed tokens** as a shared prefix before the random context. All requests share the same prefix — vLLM's prefix cache hits it, reducing prefill cost proportionally to `N / total_input_len`.

The random context portion (total input minus prefix) is sampled from `[input_len * (1-range_ratio), input_len * (1+range_ratio)]`. With `--random-range-ratio 0.1`, each request's random suffix varies ±10%.

## Key Design Decisions

1. **`--endpoint /v1/completions`** — NOT `/v1/chat/completions`. The GLM server has `--reasoning-parser glm45` active, which puts thinking in the `reasoning` field and leaves `content: null`. Benchmarks need the clean `text` field from `/v1/completions` to measure actual generation throughput.

2. **No `--trust-remote-code`** — `vllm bench serve` does not support this flag.

3. **`--backend openai-chat`** — Works with `/v1/completions` (not just chat). This backend handles the raw completions endpoint.

4. **`source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate`** — vllm only in the remote venv, not on local WSL. Script SSHs to 70.96 and runs there.

## Override Examples

```bash
# Change request rate (default: inf = burst all at once)
RATE=8 bash bench_glm5_nvfp4_prefix_cache.sh

# Fewer prompts for dry run
NUM_PROMPTS=10 bash bench_glm5_nvfp4_prefix_cache.sh

# Custom result directory
RESULT_DIR=/data/bench_results bash bench_glm5_nvfp4_prefix_cache.sh
```

## Output Files

Each run produces:
- `${RESULT_DIR}/${label}_${TIMESTAMP}.json` — main result JSON
- `${RESULT_DIR}/${label}_${TIMESTAMP}.log` — full stdout/stderr log

Summary table is printed at end of run: Requests, Completed, req/s, tok/s, TTFT p50/p99, TPOT p50/p99, E2EL p50/p99.

## Results Location

Default: `/tmp/vllm_bench_results/` — both locally and on remote (same path, since script runs on remote).