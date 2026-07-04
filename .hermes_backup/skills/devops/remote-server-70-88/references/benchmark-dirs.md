# Benchmark Directories on 70.88

## Standard Layout

Each model has its own dir under `/home/jianliu/work/bench_test/`:

```
deepseekv4_flash/
  start_dsv4_flash_1node.sh    # vLLM single-node TP=8 startup
  test_deepseekv4_throughput_cache.py  # throughput + cache benchmark
  run_benchmark.sh              # wrapper: cache 0/40/80%, 200 req, conc 64
  results/                       # JSON results per run

qwen_3_6/
  start_qwen36.sh               # DP=8, EP, FP8 (working config)
  start_qwen36_1node.sh         # TP8+EP on single-node (FAILS with FP8, see below)

minimax_m2_7/
  start_minimax_m2_nvfp4_tpep.sh  # TP=8 + EP, copied from 70.95

wan_2_2_nvfp4/
  generate                       # SGLang generate CLI
  test_wan22_nvfp4_backends.sh  # backend comparison benchmark

qwen_image_2512/
  test_qwen_image_benchmark.py
  qwen_image_multigpu_server.py
  qwen_image_benchmark_results/
```

## Standardized Bench Script (vllm_bench_standard_test/)

Located at: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/`

This directory contains `run_vllm_bench_serve.sh` (wrapper) and `test_vllm_bench_serve.py` (Python driver that calls `vllm bench serve`).

### Key env vars for run_vllm_bench_serve.sh

| Env Var | Default | Description |
|---------|---------|-------------|
| `MODEL` | `/home/jianliu/work/models/deepseekv4_flash` | Local tokenizer path (also used as --model) |
| `TOKENIZER` | Same as MODEL | Tokenizer path for bench tool |
| `TOKENIZER_MODE` | `deepseek_v4` | **Must override for non-DeepSeek models** (use empty string or `auto` for Qwen) |
| `SERVED_MODEL_NAME` | (none) | Override model ID sent to API (needed for Docker-served models) |
| `REQUESTS` | 200 | Number of benchmark requests |
| `CONCURRENCY` | 64 | Max concurrent requests (set to 1 for single-batch/latency tests) |
| `INPUT_TOKENS` | 2048 | Input token length |
| `OUTPUT_TOKENS` | 500 | Output token length |
| `CACHE_HIT_RATES` | `0,0.4,0.8` | Comma-separated cache hit rates to test |
| `BACKEND` | `openai` | vLLM bench backend (use `openai` for /v1/completions) |
| `BASE_URL` | `http://127.0.0.1:8000` | Server endpoint |
| `MODEL_LABEL` | Model path basename | Label for result files |
| `WARMUPS` | 1 | Warmup requests before measurement |

### Important notes

- **TOKENIZER_MODE default**: The script defaults to `deepseek_v4` which is wrong for Qwen models. Set `TOKENIZER_MODE=` (empty) or `TOKENIZER_MODE=auto` for non-DeepSeek models.
- **SSH env var escaping**: The Hermes terminal tool sanitizes certain strings in SSH commands (replacing them with `***`). Use base64 encoding or write a remote script file to avoid this.
- **Results directory**: `~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/vllm_bench_results/<timestamp>/`

## Throughput Benchmark Pattern (legacy)

All throughput benchmarks use `test_<model>_throughput_cache.py`. Key conventions:

1. **`--base-url`** must be `http://localhost:8000` — script appends `/v1/chat/completions` internally. Do NOT pass `/v1/completions` or `/v1/chat/completions` as base-url (causes HTTP 404).
2. **`--cache-hit-rate`** is a float: `0.0`, `0.4`, `0.8`.
3. **`--save-json`** saves detailed results to the specified path.
4. **80% cache runs are slow** — set `--request-timeout 900` or run separately outside loops.

## Copying Test Dirs from 70.88

```bash
# To local Downloads
scp -r jianliu@10.10.70.88:/home/jianliu/work/bench_test/<dir> "/mnt/c/Users/liuch/Downloads/"

# Between servers
scp -r jianliu@10.10.70.88:/home/jianliu/work/bench_test/<dir> jianliu@10.10.70.95:/home/jianliu/work/bench_test/
```
