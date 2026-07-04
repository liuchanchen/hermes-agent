# vllm bench serve — Full Reference

## Tool Location
```
/data/venvs/vllm-ds4/bin/vllm bench serve
```

Not `vllm serve bench` — the subcommand is `bench serve`.

## Critical Flag Names (Non-Obvious)

`vllm bench serve` flags are non-obvious — the `--help` is terse and many flag names differ from expectations:

| Wrong (will fail or error) | Correct | Error on wrong flag |
|---------------------------|---------|---------------------|
| `--dataset` | `--dataset-name` | `ambiguous option: --dataset could match --dataset-name, --dataset-path` |
| `--concurrency` | `--max-concurrency` | `unrecognized arguments: --concurrency` |
| `--output-json` | `--result-dir` + `--label` | `unrecognized arguments: --output-json` |
| `--random-output` | `--random-output-len` | `unrecognized arguments: --random-output` |

**Model name `--model` must match the served name, not the filesystem path:**
```bash
# WRONG — filesystem path causes HTTP 404 "Not Found" for ALL requests:
--model /data/models/glm_5_1_nvfp4/

# CORRECT — use the served model name from /v1/models:
--model glm5_1_fp8
```

To find the served model name:
```bash
curl -s http://localhost:8000/v1/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"
```

## Datasets

| Dataset | Key Args | Use Case |
|---------|----------|----------|
| `random` | `--random-input-len`, `--random-output-len`, `--random-prefix-len` | Cold cache / 0% cache hit |
| `prefix_repetition` | `--prefix-repetition-num-prefixes`, `--prefix-repetition-prefix-len`, `--prefix-repetition-suffix-len` | Prefix caching / controlled cache hit rate |
| `sharegpt` | `--sharegpt-file` | Multi-turn conversations |
| `hf-chat` | `--hf-chat-file` | HuggingFace chat format |

### random Dataset
```
--dataset-name random
--random-input-len 2048           # input tokens
--random-output-len 512           # output tokens
--random-prefix-len 0             # 0 = no prefix (pure cold); non-zero = shared prefix length
```

### prefix_repetition Dataset
```
--dataset-name prefix_repetition
--prefix-repetition-num-prefixes 384   # N shared prefixes across num-prompts requests
--prefix-repetition-prefix-len 512     # tokens per prefix (cached portion)
--prefix-repetition-suffix-len 1536    # tokens per suffix (unique per request)
--random-output-len 512
```

**Cache hit rate formula** for `prefix_repetition`:
```
cache_hit_rate = (num_prompts - num_prefixes) / num_prompts
```

| Scenario | Input Total | Prefix | Suffix | Output | Cache Hit | num_prefixes |
|----------|-----------|--------|--------|--------|-----------|-------------|
| A1 | 2048 | 512 | 1536 | 512 | 0% | use `random` |
| A2 | 2048 | 512 | 1536 | 512 | 40% | 384 |
| A3 | 2048 | 512 | 1536 | 512 | 80% | 128 |
| B1 | 60000 | 512 | 59488 | 512 | 0% | use `random` |
| B2 | 60000 | 512 | 59488 | 512 | 40% | 384 |
| B3 | 60000 | 512 | 59488 | 512 | 80% | 128 |

## Metrics

### Built-in Percentile Metrics
```
--percentile-metrics ttft,tpot,itl --metric-percentiles 50,90,99
```

| Metric | Full Name | What It Measures |
|--------|-----------|-----------------|
| TTFT | Time To First Token | Prefill + first decode token latency |
| TPOT | Time Per Output Token | Total time / output tokens (lower = faster decode) |
| ITL | Inter-Token Latency | Time between consecutive decode tokens |

**TTFT is the strongest signal for prefill-bound workloads** (long prompts, prefix cache).

### Computing Throughput from Result JSON

The result JSON (`--save-result --result-dir`) contains per-request data:

```python
import json

with open("/data/bench_results/SCENARIO.json") as f:
    d = json.load(f)

# Output throughput (tokens/sec)
total_output = sum(r["output_tokens"] for r in d["requests"])
total_time = d["total_time"]
output_tput = total_output / total_time

# Decode throughput approximation
# (TTFT covers prefill; decode_time ≈ total_time - ttft for each request)
decode_tokens = sum(r["output_tokens"] for r in d["requests"])   # same as total_output for completion tasks
# Use prefill-throughput from the JSON if available
print(f"Output throughput: {output_tput:.2f} tok/s")
```

## Concurrency vs. num-prompts

- `--max-concurrency N`: max simultaneous in-flight requests
- `--num-prompts M`: total requests to send
- For a server with `--max-num-seqs 64`, set concurrency=64 to saturate

## Background Launch Pattern

### Problem
`ssh host 'cmd &'` hangs — SSH waits for the backgrounded child.
`nohup cmd &` via SSH also hangs — same reason.
`terminal(background=true)` works but process status is opaque.

### Solution: setsid + fd redirect
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && \
  setsid /data/venvs/vllm-ds4/bin/vllm bench serve \
    --tokenizer /data/models/<model>/ \
    ...args... \
    </dev/null >/tmp/bench.log 2>&1 & echo LAUNCHED:\$!"
```
`</dev/null` detaches stdin. `>/dev/null 2>&1` detaches stdout/stderr (log to file instead). `&` still backgrounds, but setsid creates a new session so SSH returns immediately.

### Verification
```bash
# Check process is alive
ssh jianliu@10.10.70.96 "ps aux | grep 'vllm bench' | grep -v grep"

# Check GPU activity (running = ~100%, dead = ~0%)
ssh jianliu@10.10.70.96 "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader"
```

### Process Health Check via GPU

vllm bench serve tqdm progress is not written to the log file when `--disable-tqdm` is set — you cannot `tail -f log | grep 50%`. Instead, GPU utilization is a reliable proxy:
- **100% GPU util**: benchmark actively running (decode/prefill)
- **0% GPU util**: process died silently or engine deadlocked → see Failure Modes below
- **High memory + 0% util**: server idle (no requests in flight) or engine core deadlocked

## Warmup

vLLM's first inference includes JIT compilation (Triton kernels). This can add 3–6s to TTFT. Always do a warmup request before timed runs:

```bash
curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<model>","prompt":"hi","max_tokens":10}' > /dev/null
```

## Sequential Orchestration

For multi-scenario benchmarks on a single server, run sequentially:

```python
#!/usr/bin/env python3
"""Sequential benchmark orchestrator — runs on remote server."""
import subprocess, json, time, os

SCENARIOS = [
    # (label, extra_args)
    ("A1_2k_0pct",   "--dataset-name random --random-input-len 2048 --random-output-len 512 --random-prefix-len 0"),
    ("A2_2k_40pct",  "--dataset-name prefix_repetition --prefix-repetition-num-prefixes 384 --prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 --random-output-len 512"),
    ("A3_2k_80pct",  "--dataset-name prefix_repetition --prefix-repetition-num-prefixes 128 --prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 --random-output-len 512"),
    ("B1_60k_0pct",  "--dataset-name random --random-input-len 60000 --random-output-len 512 --random-prefix-len 0"),
    ("B2_60k_40pct", "--dataset-name prefix_repetition --prefix-repetition-num-prefixes 384 --prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 59488 --random-output-len 512"),
    ("B3_60k_80pct", "--dataset-name prefix_repetition --prefix-repetition-num-prefixes 128 --prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 59488 --random-output-len 512"),
]

BASE_ARGS = "--base-url=http://localhost:8000 --endpoint=/v1/completions --model glm5_1_fp8 --tokenizer /data/models/glm_5_1_nvfp4/ --max-concurrency 64 --num-prompts 640 --percentile-metrics ttft,tpot,itl --metric-percentiles 50,90,99 --save-result --result-dir /data/bench_results"

for label, extra in SCENARIOS:
    result_file = f"/data/bench_results/{label}.json"
    log_file = f"/tmp/bench_{label}.log"
    cmd = f"/data/venvs/vllm-ds4/bin/vllm bench serve {BASE_ARGS} --result-filename {label}.json {extra} > {log_file} 2>&1"
    
    print(f"[{label}] Launching...")
    subprocess.run(f"pkill -f 'vllm bench serve'; sleep 2", shell=True)
    subprocess.run(f"setsid bash -c 'source ~/.bashrc && {cmd}' </dev/null >/dev/null 2>&1 &", shell=True)
    
    # Poll until result file appears or timeout
    deadline = time.time() + 900  # 15 min timeout per scenario
    while time.time() < deadline:
        if os.path.exists(result_file):
            with open(result_file) as f:
                d = json.load(f)
            print(f"[{label}] Done — {len(d['requests'])} requests")
            break
        time.sleep(15)
    else:
        print(f"[{label}] TIMEOUT — check {log_file}")
```

Save to `/tmp/bench_orch_server.py` on the remote, launch via:
```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && setsid python3 /tmp/bench_orch_server.py </dev/null >/dev/null 2>&1 &"
```

## Key Flag Reference

| Flag | Notes |
|------|-------|
| `--tokenizer` | **Always set** — local path to avoid HF network lookup |
| `--dataset-name` | `random` or `prefix_repetition` — NOT `--dataset` |
| `--max-concurrency` | NOT `--concurrency` |
| `--random-input-len` | Input token count (random dataset) |
| `--random-output-len` | Output token count — NOT `--random-output` |
| `--random-prefix-len` | Shared prefix length before random suffix (0 = pure cold) |
| `--prefix-repetition-prefix-len` | Cached prefix tokens |
| `--prefix-repetition-suffix-len` | Unique suffix = total_input - prefix_len |
| `--prefix-repetition-num-prefixes` | N unique prefixes; cache_hit = (num_prompts - N) / num_prompts |
| `--result-dir` | Output dir — combine with `--label`, NOT `--output-json` |
| `--label` | Result file prefix; actual file is `{label}.json` |
| `--model` | **Must be served model name**, NOT filesystem path |
| `--percentile-metrics` | Comma-separated: `ttft,tpot,itl` |
| `--metric-percentiles` | Comma-separated: `50,90,99` |
| `--save-result` | Write JSON to `--result-dir` |
| `--result-filename` | Output filename (no .json extension needed) |
| `--num-prompts` | Total requests; cache hit rate formula uses this |
| `--disable-tqdm` | Suppress progress bar (cleaner logs) |
| `--no-stream` | Non-streaming (required for accurate TTFT measurement) |

## Failure Modes

### 1. Server Hang on Deep Inputs (60k+ tokens at high concurrency)

**Symptom**: Benchmark launches with correct flags, server responds to `/v1/models` and short prompts, but `/v1/completions` hangs for all requests. Even a 4-token `hi` request times out after the benchmark starts running.

**Root cause**: 60k token prefill × 64 concurrent requests exhausts KV cache → NCCL/Gloo communication deadlock in distributed engine workers. The API server survives (accepts TCP connections) but the engine core is frozen.

**Diagnosis**:
```bash
# These still respond — API server alive:
curl -s --max-time 5 http://localhost:8000/v1/models      # OK

# This hangs — engine core deadlocked:
curl -s --max-time 10 -X POST http://localhost:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":4,"temperature":0}'

# GPU memory full but util 0%:
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits -i 0
# → 90919, 0  (VRAM full, no compute)
```

**Recovery**: Server self-recovers after 2–3 minutes. If not, full restart needed. **Wait 3 minutes before assuming permanent failure.**

**Mitigation for 60k scenarios**:
- Reduce `--max-concurrency` from 64 → 8–16
- Reduce `--random-input-len` from 60000 → 30000
- Use `--random-prefix-len` to add a shared prefix (reduces unique per-request KV cache)
- Smoke test a single 60k request before launching the full benchmark

**Note**: A single 60k request completes successfully (~7.5s). The failure only occurs under concurrent load. The issue is **concurrent prefill of 60k-class inputs**, not the 60k length itself.

### 2. "Not Found" for All 640 Requests — Model Name Mismatch

**Symptom**: All 640 requests fail immediately with HTTP 404 "Not Found". Benchmark reports `Successful: 0, Failed: 640` in ~2 seconds.

**Root cause**: `--model` set to the filesystem path instead of the served model name.

**Fix**: Use `--model <served_name>` matching `/v1/models`:
```bash
curl -s http://localhost:8000/v1/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"
```

### 3. `random` Dataset Stalls on GLM Models

On GLM-family models (GLM-5.1-NVFP4, GlmMoeDsaForCausalLM), the `random` dataset with `--random-prefix-len 0` causes the benchmark to stall at `0/640` with 100% GPU utilization — but no requests ever complete.

**Root cause**: GLM tokenizer assigns `[gMASK]` as one of the most common random token IDs. When `[gMASK]` is the first generated token, the model enters "generative" mode that waits for a `sop` token, causing decode deadlock.

**Fix**: Use `--dataset-name prefix_repetition` with `--prefix-repetition-num-prefixes 640 --prefix-repetition-prefix-len 0 --prefix-repetition-suffix-len <input_len>` instead of the `random` dataset. This uses real tokenizer-generated prompts and avoids the `[gMASK]` token.

### 4. GPU 0% + Bench Log Stuck at Config Dump

**Symptom**: Log has only 5 lines (namespace dump + `Sampling input_len`), no progress, no error. Bench process is alive (CPU 100%) but server shows 0% GPU util.

**Diagnosis**:
```bash
# Process alive:
ps aux | grep 'vllm bench' | grep -v grep

# Has TCP connections to server:
ss -tnp | grep <pid>

# GPU util 0% + VRAM full:
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits -i 0
# → 90919, 0
```

Typically the server deadlock (Failure Mode #1). See above for recovery.

## Known Issues

1. **Tokenizer download hang**: If `--tokenizer` is missing and the venv cannot reach HuggingFace, the tool hangs forever at "Loading tokenizer". Fix: always set `--tokenizer`.

2. **Sequential runs need cleanup**: Before each new scenario, `pkill -f 'vllm bench serve'` to kill the previous run's processes, otherwise they accumulate and starve GPU memory.

3. **Long prompts + high concurrency = slow throughput**: At 60k input + concurrency 64, the server may deadlock. See Failure Mode #1.