# vLLM Bench Serve — Patterns & Gotchas (GLM-5.1-NVFP4 context)

## Backend vs Endpoint matching (critical)

| Backend flag | Required endpoint | Works for GLM reasoning? |
|---|---|---|
| `--backend openai-chat` | `/v1/chat/completions` | Yes, but `content: null` with `--reasoning-parser glm45` |
| `--backend openai` | `/v1/completions` | **Yes** — clean output without reasoning |

**Rule**: For throughput benchmarks on a GLM server with `--reasoning-parser glm45` active, always use `--backend openai` + `--endpoint /v1/completions`. Using `openai-chat` against `/v1/completions` fails with `ValueError: OpenAI Chat Completions API URL must end with one of: {'chat/completions', 'profile'}`.

## Tokenizer setup (prevents hangs)

vllm bench serve encodes synthetic prompts using the model tokenizer **locally** (wherever the bench runs). If the tokenizer can't be fetched from HuggingFace, the process hangs forever on retry loops.

For 70.96, always set:
```bash
export HF_HUB_OFFLINE=1                        # block HuggingFace network calls
--tokenizer /data/models/glm_5_1_nvfp4/        # local tokenizer path
--tokenizer-mode slow                           # avoid auto-detect hangs
```

Without these, expect: `Error retrieving file list: [Errno 101] Network is unreachable` followed by multi-minute retry hangs.

## Prefix cache hit rate

The `--random-prefix-len N` flag adds **N fixed tokens** as a shared prefix before the random suffix per request. All requests share the same prefix, so the cache hit rate is:

```
cache hit rate ≈ --random-prefix-len / --random-input-len
```

Examples for input_len=2048:
- 0%  → `--random-prefix-len 0`
- 40% → `--random-prefix-len 819`   (819/2048 ≈ 40%)
- 80% → `--random-prefix-len 1638`  (1638/2048 ≈ 80%)

## Known failure: engine deadlock under benchmark load

Under heavy benchmark load (500 prompts, concurrency=64, burst rate=inf), the GLM server engine can deadlock — `/v1/models` still returns 200 but `/v1/completions` and `/v1/chat/completions` both hang indefinitely.

**Signature**:
```
curl http://localhost:8000/v1/models         → 200 OK (API alive)
curl -X POST http://localhost:8000/v1/completions → timeout (engine dead)
```

**Fix**: Kill all vLLM processes, clear Triton cache, restart:
```bash
pkill -9 -f vllm; sleep 3; rm -rf /root/.triton/cache; nvidia-smi --query-gpu=memory.used
# Verify GPU freed to ~14 MiB/card, then restart
```

**Recovery**: Run the startup script:
```bash
sudo bash /data/model_startup_script/start_glm5_nvfp4_docker.sh
```

## Concurrency and request rate

- `--request-rate inf` = burst mode (all requests fired simultaneously)
- `--max-concurrency N` = cap on concurrent in-flight requests
- When used together, actual RPS is capped by `max_concurrency` even if `request_rate` would produce more

For 70.96 benchmarks, default is `--max-concurrency 64` + `--request-rate inf`.

## Other useful flags

```bash
--num-prompts 500        # number of synthetic requests
--num-warmups 1          # warmup runs before measurement
--random-range-ratio 0.1  # ±10% variation in input/output length
--save-detailed          # save full per-request timing data
--disable-tqdm           # suppress progress bar (clean logs)
--disable-shuffle        # deterministic ordering
--save-result --result-dir /path/to/results  # JSON result file
```