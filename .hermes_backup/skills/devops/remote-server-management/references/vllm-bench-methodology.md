# vLLM Benchmark & Throughput Tuning Methodology

<!--- Methodology captured from multi-node DeepSeek V4 Pro tuning session (2026-05-25) --->

## Benchmark Tool Usage

### Chat Endpoint (correct invocation)

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
vllm bench serve \
  --backend openai-chat \
  --endpoint /v1/chat/completions \
  --tokenizer /path/to/model/tokenizer \  # local path to avoid HF download
  --model /path/to/model \                # local path, or served model name
  --dataset-name random \
  --random-input-len 128 \
  --random-output-len 128 \
  --num-prompts 10 \
  --request-rate inf \
  --temperature 0 \                        # explicit, default is NOT greedy
  --save-result \
  --result-dir /tmp/vllm_bench \
  --result-filename result.json \
  --disable-tqdm
```

### Critical flags

| Flag | What it does | Gotcha |
|------|-------------|--------|
| `--random-input-len` | Sets input prompt length for `random` dataset | NOT `--input-len` (that's for `custom` dataset) |
| `--random-output-len` | Sets output generation length | (same) |
| `--backend openai-chat` | Sends chat completion format instead of text completion | Required for chat-tuned models |
| `--temperature 0` | Forces greedy decoding | Without it, server default applies |
| `--tokenizer /path` | Local tokenizer path | Required on offline servers; model name alone triggers HF download |
| `HF_HUB_OFFLINE=1` | Prevents HF from trying to connect | Prevent 5-min timeout waiting for network |
| `--save-result` | Saves detailed JSON to `--result-dir` | Directory is auto-created |

### Prefix-cache benchmark

Uses `prefix_repetition` dataset (note dashes in the long form):

```bash
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 60000 \   # shared prefix (cache hit)
--prefix-repetition-suffix-len 128 \     # unique suffix (cache miss)
--prefix-repetition-num-prefixes 5 \     # N distinct prefixes (1 = all same)
```

### Output metrics of interest

From the JSON result file:

```json
mean_ttft_ms           // Time to First Token (prefill latency)
mean_tpot_ms           // Time Per Output Token (decode latency)
mean_itl_ms            // Inter-Token Latency (scheduling jitter)
output_throughput      // tok/s at the output
request_throughput     // req/s
total_token_throughput // input+output tok/s (prefill + decode combined)
```

## Tuning Dimensions (cost to change)

### Phase 1: Zero-restart (change benchmark flags only)

| Parameter | Effect | Test |
|-----------|--------|------|
| `--request-rate inf` | All-burst, max contention | Baseline |
| `--request-rate 0.5` | 2s between requests, no queueing | Better TTFT, lower throughput |
| `--dataset-name prefix_repetition` | Measure prefix cache effectiveness | See above |
| `--num-prompts N` | Increase concurrency pressure | Scales throughput |

### Phase 2: Requires restart — max-num-batched-tokens & max-num-seqs

| batched-tokens | seqs | Effect |
|---------------|------|--------|
| 8192 | 128 | Lowest TTFT, lower decode throughput |
| 16384 | 256 | Balanced (typical baseline) |
| 32768 | 128 | Good for long-prompt prefill |
| 32768 | 256 | Higher throughput, higher TTFT |

Must also update:
- `compile_ranges_endpoints` in `--compilation-config` to include the new batched-token value
- CUDA graph capture sizes are auto-derived from `max-num-seqs`

### Phase 3: Requires restart — compilation mode

| `compilation-config.mode` | Cost | Benefit |
|---------------------------|------|---------|
| 0 | Slow execution, no torch.compile | Fast startup, no JIT spikes |
| 3 (VLLM_COMPILE) | 5+ min startup | 1.5-2x throughput improvement |

### Known limits

- **DP handshake timeout hardcoded at 300s** in `vllm/v1/engine/core.py` (line 1046). Large models + compilation mode 3 + cudagraph profiling can exceed this. No CLI flag to override. Workaround: reduce compilation load (fewer `custom_ops`, narrower `compile_ranges_endpoints`), or patch the timeout in source.
- **`--api-server-count` cannot be used with `--headless`** — the worker has no API server. Only valid on master.
- **Default `api_server_count` = `data_parallel_size`** — without explicit `--api-server-count`, it matches DP size. With DP=2, this launches 2 API servers which auto-disables engine stats logging.

## Test Matrix Template

```
Host configuration saved in /tmp/launch_vllm.sh on each node.
Results saved to /tmp/vllm_bench_report/*.json

For each configuration:
  1. Update launch scripts on all nodes
  2. Kill all vLLM processes on all nodes
  3. Clean GPU memory: nvidia-smi | grep VLLM → kill -9 PID
  4. Start worker first, then master
  5. Wait for "Application startup complete" on master (poll v1/models)
  6. Send warmup request, then run S1, S2, S3 benchmarks
```

## S3 Prefix Cache Probability Test (manual Python)

For measuring prefix cache hit/miss behavior with arbitrary shared prefixes (not the `prefix_repetition` dataset):

Send N streaming requests sharing a long common prefix. Request 0 is cold (full prefill). Requests 1..N-1 should hit cache:

```python
import requests, time
BASE = "http://localhost:8000/v1/chat/completions"
prefix = "What is " * 1800  # ~1800 tokens
for i, suffix in enumerate(["? A", "? B", "? C", "? D"]):
    t0 = time.time(); first = None
    r = requests.post(BASE, json={"model":"m","messages":[{"role":"user","content":prefix+suffix}],"max_tokens":128,"stream":True}, stream=True, timeout=600)
    for line in r.iter_lines():
        if line and line.startswith(b"data: ") and line != b"data: [DONE]":
            if first is None: first = time.time()
    print(f"Req {i}: TTFT={(first-t0)*1000:.0f}ms")
# Req 0: cold ~5000ms, Req 1+: cache hit ~400ms
```
