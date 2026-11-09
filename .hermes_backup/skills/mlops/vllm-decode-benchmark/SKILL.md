---
name: vllm-decode-benchmark
description: Run decode throughput benchmarks via vllm bench serve.
version: 0.1.0
author: Hermes
---

# vLLM Decode Throughput Benchmark

Run decode-focused serving benchmarks using `vllm bench serve` against a running
vLLM server. Uses the completions API (`--backend openai`) so that output token
counts are correctly reported in the results JSON. Supports custom semantic
JSONL datasets with variable-length prompts and configurable output lengths.

## When to Use

- Compare decode throughput between server configurations (TP vs DP, MTP on/off).
- Measure TTFT, TPOT, ITL, and E2E latency at a given concurrency level.
- Validate that a config change (gpu-memory-utilization, block-size, MTP) improves
  or degrades decode throughput.
- Generate a repeatable, saved JSON result for comparison or reporting.

## Prerequisites

- A running vLLM server reachable at `BASE_URL` (default `http://127.0.0.1:8000`).
- The vLLM venv at `VENV_PATH` (default `/data/venvs/vllm-ds4`) with `vllm bench`
  subcommand available.
- A JSONL dataset with `{"prompt": "...", "output_tokens": N}` per line.

## How to Run

Invoke the shell script through the `terminal` tool with env var overrides:

```bash
MODEL=glm5_2_nvfp4 \
  TOKENIZER=/data/models/glm_5_2_nvfp4/ \
  TOKENIZER_MODE=auto \
  TRUST_REMOTE_CODE=1 \
  bash run_vllm_decode_bench_serve.sh --skip-tokenizer-init
```

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL` | `/home/jianliu/work/models/deepseekv4_flash` | Model name/path sent in API requests |
| `TOKENIZER` | `$MODEL` | Tokenizer path for client-side counting |
| `BACKEND` | `openai` | `openai` → `/v1/completions`, `openai-chat` → `/v1/chat/completions` |
| `REQUESTS` | `80` | Number of prompts to send |
| `CONCURRENCY` | `16` | Max concurrent requests |
| `OUTPUT_TOKENS` | `512` | `max_tokens` per request |
| `SAVE_DETAILED` | `0` | Set `1` to save per-request latencies/tokens |
| `CLEAR_LD_PRELOAD` | `1` | Clears `LD_PRELOAD` to avoid xplatform preload conflicts |
| `BYPASS_LOCAL_PROXY` | `1` | Sets `NO_PROXY` to skip local proxy for loopback traffic |

## Quick Reference

```bash
# Minimal invocation (DeepSeek V4 Flash defaults)
bash run_vllm_decode_bench_serve.sh

# Single-stream decode (concurrency=1 — measure uncontended per-stream TPOT)
CONCURRENCY=1 bash run_vllm_decode_bench_serve.sh

# GLM-5.2 with skip-tokenizer-init (needed when transformers can't load config)
MODEL=glm5_2_nvfp4 TOKENIZER=/data/models/glm_5_2_nvfp4/ \
  TOKENIZER_MODE=auto TRUST_REMOTE_CODE=1 \
  bash run_vllm_decode_bench_serve.sh --skip-tokenizer-init

# Non-MTP vs MTP2 comparison
CONCURRENCY=32 REQUESTS=256 bash run_vllm_decode_bench_serve.sh

# With detailed per-request output
SAVE_DETAILED=1 CONCURRENCY=2 REQUESTS=4 bash run_vllm_decode_bench_serve.sh

# Dry run (prints the vllm command without executing)
DRY_RUN=1 bash run_vllm_decode_bench_serve.sh
```

## Procedure

### 1. Verify the server is healthy

```bash
curl -s http://127.0.0.1:8000/health
```

### 2. Run the benchmark

Set `CONCURRENCY` and `REQUESTS` to match the test plan. For decode-focused
benchmarks, set `IGNORE_EOS=1` (default) so that every request generates exactly
`OUTPUT_TOKENS` tokens.

```bash
cd /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test
CONCURRENCY=32 REQUESTS=256 \
  MODEL=glm5_2_nvfp4 \
  TOKENIZER=/data/models/glm_5_2_nvfp4/ \
  TOKENIZER_MODE=auto \
  TRUST_REMOTE_CODE=1 \
  bash run_vllm_decode_bench_serve.sh --skip-tokenizer-init
```

### 3. Read the results

The script prints a summary table. The result JSON is saved to:

```
vllm_bench_results/decode_<timestamp>/<model>_<output_tokens>out_decode_conc_<concurrency>_<timestamp>.json
```

Key fields: `total_output_tokens`, `mean_e2el_ms`, `median_e2el_ms`,
`p50/p90/p95/p99_e2el_ms`, `request_throughput`, `output_throughput`.

### 4. Compare two runs

Use Python to load both result JSONs and compare:

```python
import json
with open("run1.json") as f: d1 = json.load(f)
with open("run2.json") as f: d2 = json.load(f)
print(f"MTP2 speedup: {d2['request_throughput']/d1['request_throughput']:.2f}x")
```

## Backend Selection (Critical for Correct Token Counting)

The `--backend` flag determines which API endpoint is used and how streaming
chunks are parsed:

- **`openai`** (default, recommended): Uses `/v1/completions`. Streaming chunks
  contain `choices[0].text`. The usage chunk at the end correctly populates
  `output.output_tokens` in the benchmark code. **Use this for correct
  `total_output_tokens` in the result JSON.**

- **`openai-chat`**: Uses `/v1/chat/completions`. Models using reasoning
  format (GLM-5.2 with `reasoning-parser glm45`) emit `delta.reasoning` and
  `delta.content` in streaming chunks, but the benchmark reads
  `choices[0].get("text")` which never matches. With `--skip-tokenizer-init`,
  the fallback path sets `output_len=1`, producing `total_output_tokens=N` (one
  per request) instead of the true count.

## Dataset Format

The dataset is a JSONL file (one JSON object per line):

```json
{"prompt": "Incident memo INC-20260708: ...", "output_tokens": 512}
```

Build a custom dataset with the builder script at
`datasets/build_decode_semantic_dataset.py`. It generates 256 engineering-memo
prompts of varying lengths (128–800 input tokens) across 16 LLM-serving domains.

## Pitfalls

### MTP OOM on 8× RTX 5090 (32GB)
DeepSeek-V4-Flash MTP mode cannot fit on 8× RTX 5090 (32GB each) at gpu_memory_utilization=0.9735. Model weights alone consume ~18.6GB/GPU, CUDA graphs ~4.88GB, leaving only ~70 MiB free — sampler warmup fails with CUDA OOM. Workaround: use non-MTP mode, or reduce max-model-len (from 262k) / lower gpu_memory_utilization / add more GPUs.

### Concurrency scaling behaviour
See `references/decode-concurrency-scaling-dsv4-flash.md` for empirical data on DeepSeek-V4-Flash across concurrency levels (conc=1, 16, 64). Key findings after clean server restart: per-stream TPOT at conc=1 is **10.28ms** (~97 tok/s per stream). Degrades ~1.4× (conc=16) to ~3.2× (conc=64) vs baseline, but aggregate throughput increases 10.4× (conc=16) to 18.9× (conc=64).

### Restart server before benchmarking for clean results
**Critical**: A clean server restart produces measurably different TPOT numbers than a server that has been running or one that started from a "warm" AOT compile cache. For reproducible comparisons:

1. Kill ALL vLLM processes (API server + VLLM:: worker zombies + multiproc executors):
   ```bash
   ps aux | grep -E "vllm serve|VLLM::|EngineCore|multiproc_executor" | grep -v grep | awk '{print \$2}' | xargs -r kill -9
   ```
2. Verify GPU memory freed to ~15 MiB baseline:
   ```bash
   nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
   ```
3. Start fresh with the canonical script
4. Wait for `Application startup complete` + `Health: 200`
5. The benchmark's built-in initial single prompt run serves as warm-up — no separate warm-up needed

### Concurrency env vars
The decode bench script uses these env var overrides (verify before each run):
- `CONCURRENCY` — max concurrent requests (default 16)
- `REQUESTS` — number of prompts (default 80)
- `OUTPUT_TOKENS` — max_tokens per request (default 512)
- `MODEL_LABEL` — label for result filename

### ASL (agent sidecar library) kill-blocked processes
When using `nvidia-smi` to free GPU memory, the ASL
process can block GPU memory release. Kill it with:
```bash
kill -9 $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | sort -u | grep -v '^$')
```

- **`--skip-tokenizer-init` is needed when `transformers` can't load the model
  config** (e.g. GLM-5.2 with `deepseek_sparse_attention` layer types). Without
  it, the benchmark crashes at startup before any requests are sent.
- **`total_output_tokens` will be N (one per request) if using `--backend
  openai-chat`** with models that emit reasoning-format deltas. Switch to
  `--backend openai` for correct counting.
- **The `CLEAR_LD_PRELOAD` and `BYPASS_LOCAL_PROXY` defaults** are set to 1
  because many shipping environments inject xplatform preload libraries or set
  HTTP proxies that break localhost connections. Set both to 0 if the env is
  clean.
- **Long `max-model-len` + high concurrency → OOM.** Reduce `CONCURRENCY` or
  increase `--gpu-memory-utilization` on the server side.
- **`--disable-shuffle` is enabled by default** to keep the prompt order
  deterministic across runs. Remove for random-order testing.
- **MTP speculative decoding benefit is concurrency-dependent.** At low
  concurrency (GPU not saturated), MTP overhead may cancel or exceed the
  benefit — non-MTP can be as fast or faster. Only test MTP at the target
  production concurrency level. See `references/mtp-scaling-behavior.md` for
  empirical GLM-5.2-NVFP4 data showing MTP2 going from 0.97x (conc=16) to
  1.68x (conc=32).

## Verification

Check that the result JSON has correct `total_output_tokens`:

```python
import json
with open("result.json") as f:
    d = json.load(f)
print(f"Requests: {d['completed']}, Output tokens per req: {d['total_output_tokens']/d['completed']:.0f}")
```

If the value is `1`, the wrong backend was used.
