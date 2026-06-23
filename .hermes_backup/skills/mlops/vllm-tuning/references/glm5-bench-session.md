# GLM-5.1-NVFP4 Benchmark Session (2026-06-04)

Full session log from the first attempted benchmark run for GLM-5.1-NVFP4 on 10.10.70.96.

## Environment

- Server: 10.10.70.96 (jianliu), 8× RTX PRO 6000 Blackwell SE (97.9 GiB/card)
- vLLM: ds4-sm120 branch (v0.6.0.dev0), Docker-free venv at `/data/venvs/vllm-ds4`
- Model: GLM-5.1-NVFP4 (GlmMoeDsaForCausalLM) at `/data/models/glm_5_1_nvfp4/`
- API server: PID 381662, running at `http://localhost:8000`
- No external network from venv (HuggingFace.co + hf-mirror.com both unreachable)

## Command That Stalled (All 6 Scenarios — exit 255)

```bash
/data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \
  --tokenizer /data/models/glm_5_1_nvfp4/ \
  --dataset-name random \
  --max-concurrency 64 \
  --num-prompts 640 \
  --random-input-len 2048 \
  --random-output-len 512 \
  --random-prefix-len 0 \
  --percentile-metrics ttft,tpot,itl \
  --metric-percentiles 50,90,99 \
  --save-result --result-dir /data/bench_results \
  --result-filename A1_2k_0pct.json
```

Exit code 255, 0/640 progress, GPU at 97-100% but no output tokens produced.

## Root Cause: GLM Tokenizer + random Dataset

GLM's tokenizer assigns `[gMASK]` as one of the most common random token IDs. When the random token generator produces `[gMASK]` as the first token:
1. The model enters "generative masked language model" mode
2. It waits for a valid `sop` (start of planning) token
3. Without the correct continuation, the prefill completes but decode produces 0 tokens
4. All 640 requests hang in decode phase → `0/640` forever

**Evidence**: Even a minimal curl with `max_tokens=4` hangs 120+ seconds:
```
$ time curl -s --max-time 120 -X POST http://localhost:8000/v1/chat/completions \
    -d '{"model":"glm5_1_fp8","messages":[{"role":"user","content":"Hi"}],"max_tokens":4,"temperature":0}'
real    2m0.011s   # timeout
```

But `/v1/models` responds fine:
```
$ curl -s http://localhost:8000/v1/models | python3 -c '...'
glm5_1_fp8  202752
```

## Server Engine State During Stall

| Check | Result | Meaning |
|-------|--------|---------|
| `curl /v1/models` | `glm5_1_fp8` | API server alive |
| `curl /v1/completions` (4 tokens) | timeout 120s | Engine core deadlocked |
| `curl /metrics` | returns | API server alive |
| `nvidia-smi` | 97-98% GPU util, 90.8 GiB used | GPU doing computation but producing no output |
| Process count | 3× `vllm bench serve` + 8× VLLM workers + API server | All processes alive |

The old log (`/tmp/vllm_glm5_master.log`) showed the engine had previously crashed with Gloo connection errors:
```
RuntimeError: Worker failed with error '[...gloo/transport/tcp/pair.cc:547]
  Connection closed by peer [192.168.66.10]:17280'
EngineDeadError: EngineCore encountered an issue.
```

## Key Corrections from Session

1. **Server was NOT dead** — User confirmed output was still running in terminal. The GPU was at 97-98% with real computation, but the `random` dataset was causing all requests to produce zero tokens.

2. **`--tokenizer` is mandatory** — Without it, vLLM tries to reach HuggingFace network and hangs (`Network is unreachable`).

3. **`--temperature=0` is mandatory** — vLLM bench serve no longer defaults to greedy; non-zero temperature on GLM can trigger non-deterministic generation modes.

4. **`random` dataset with `--random-prefix-len 0` is incompatible with GLM** — Use `prefix_repetition` with all unique prefixes instead, or use a real prompt file via `--dataset-name hf-chat`.

5. **`pkill -9` requires user consent** — This tool is blocked by default. User must run kill commands manually on remote terminals.

## Working Benchmark Approach for GLM-5.1-NVFP4

**Do NOT use `random` dataset.** Use `prefix_repetition` for all scenarios including 0% cache:

```bash
# 0% cache (all prefixes unique):
--dataset-name prefix_repetition \
--prefix-repetition-num-prefixes 640 \
--prefix-repetition-prefix-len 0 \
--prefix-repetition-suffix-len 2048 \
--random-output-len 512 \
--temperature=0

# 40% cache:
--dataset-name prefix_repetition \
--prefix-repetition-num-prefixes 384 \
--prefix-repetition-prefix-len 512 \
--prefix-repetition-suffix-len 1536 \
--random-output-len 512 \
--temperature=0

# 80% cache:
--dataset-name prefix_repetition \
--prefix-repetition-num-prefixes 128 \
--prefix-repetition-prefix-len 512 \
--prefix-repetition-suffix-len 1536 \
--random-output-len 512 \
--temperature=0
```

## Benchmark Result File Format

Result JSON structure:
```json
{
  "config": { "model": "glm5_1_fp8", "base_url": "...", "num_prompts": 640, ... },
  "total_time": 1234.56,
  "requests": [
    {
      "request_id": "bench-xxx-0",
      "ttft": 0.123,
      "tpot": 0.045,
      "itl": 0.044,
      "output_tokens": 512,
      "latency": 23.0
    },
    ...
  ],
  "percentiles": {
    "ttft": {"50": 0.1, "90": 0.2, "99": 0.5},
    "tpot": {"50": 0.04, "90": 0.06, "99": 0.1},
    "itl": {"50": 0.04, "90": 0.06, "99": 0.1}
  }
}
```

Output throughput: `sum(r["output_tokens"]) / d["total_time"]` tokens/sec.