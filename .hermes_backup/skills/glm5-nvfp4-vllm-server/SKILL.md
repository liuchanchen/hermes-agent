---
name: glm5-nvfp4-vllm-server
category: mlops/inference
description: Start GLM-5.1-NVFP4 vLLM server on a remote GPU node via Docker
trigger: Start or deploy GLM-5.1-NVFP4 vLLM server
scripts:
scripts:
  - scripts/bench_glm5_nvfp4_prefix_cache.sh — prefix cache throughput benchmark
references:
  - references/vllm-bench-serve.md — vllm bench serve patterns, backend/endpoint gotchas, prefix cache math
  - references/bench_glm5_nvfp4_prefix_cache_fixes.md — script fixes: --backend openai, --num-warmups 0, HF_HUB_OFFLINE=1, pre-bench engine check (2026-06-08)
  - references/70-96-models.md — model download status
references:
  - references/glm5-reasoning-api-behavior.md  # GLM reasoning API (chat vs completion, content:null, reasoning_effort)
  - references/glm5-nvfp4-status.md             # server status, model config, benchmark results
---

# GLM-5.1-NVFP4 vLLM Server

## Docker Image
```
voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412
```

## 1. Enter Docker Container

```bash
sudo docker run -it --rm \
  --gpus all \
  --ipc=host \
  --shm-size=16g \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --network host \
  --entrypoint /bin/bash \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v /data:/data \
  voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412
```

## 2. Inside Container — Set Env & Start vLLM

```bash
export HF_HUB_OFFLINE=1
export VLLM_LOG_STATS_INTERVAL=1
export VLLM_ENABLE_PCIE_ALLREDUCE=1
unset VLLM_NVFP4_GEMM_BACKEND

cd /opt/vllm
exec python3 -m vllm.entrypoints.openai.api_server \
  --model /data/models/glm_5_1_nvfp4/ \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name glm5_1_fp8 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --decode-context-parallel-size 4 \
  --gpu-memory-utilization 0.82 \
  --max-num-seqs 64 \
  --kv-cache-dtype bfloat16 \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --tool-call-parser glm47 \
  --chat-template-content-format=string \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --moe-backend b12x
```

## 3. Key Parameters

| Parameter | Value | Notes |
|---|---|---|
| `--model` | `/data/models/glm_5_1_nvfp4/` | Offline mode — model must be pre-downloaded |
| `--served-model-name` | `glm5_1_fp8` | API model name |
| `--tensor-parallel-size` | `8` | 8-GPU TP |
| `--decode-context-parallel-size` | `4` | CP for decode |
| `--gpu-memory-utilization` | `0.82` | 82% GPU mem |
| `--kv-cache-dtype` | `bfloat16` | KV cache dtype |
| `--tool-call-parser` | `glm47` | Tool calling |
| `--reasoning-parser` | `glm45` | Reasoning parsing |
| `--moe-backend` | `b12x` | MoE backend |

## 4. Reasoning Behavior (Critical)

The `--reasoning-parser glm45` flag is active on this server. It **changes the output shape** of `/v1/chat/completions`:

| Field | Content |
|-------|---------|
| `reasoning` | Full chain-of-thought internal thinking |
| `content` | **null** — token budget consumed entirely by `reasoning` at high effort |

**If you need `content` with actual answer text**, use `/v1/completions` (not `/v1/chat/completions`):
```bash
curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"Why is sky blue?","max_tokens":200,"temperature":0}'
```
This bypasses the GLM reasoning/thinking machinery entirely and returns clean text in `choices[0].text`.

**`reasoning_effort` valid values** (HTTP 400 for anything else):
```
none   → reasoning=null, content has answer
low    → short reasoning (122 chars), content has short answer
medium → moderate reasoning (126 chars), content partially filled
high   → maximum detailed reasoning, content=null (budget consumed)
max    → HTTP 400 "Input should be 'none', 'low', 'medium' or 'high'"
xhigh  → HTTP 400 (same)
```
The highest level is `high`. The `reasoning_effort` parameter is independent of the server-side `--reasoning-parser` flag.

**For benchmarks**: ALWAYS use `/v1/completions` and `--backend openai` (not `--backend openai-chat`). The chat endpoint adds an extra round-trip through the GLM chat template + reasoning pipeline that distorts latency measurements and causes `content: null` issues.

## 5. Verification

> **Important:** `--reasoning-parser glm45` is active. `/v1/chat/completions` returns `reasoning` field + `content: null`. Use `/v1/completions` for clean text and health check probes. See `references/glm5-reasoning-api-behavior.md` for full endpoint behavior.

**Level 1 — API alive:**
```bash
curl -s --connect-timeout 5 http://localhost:8000/v1/models \
  | python3 -c 'import sys,json; [print(m["id"]) for m in json.load(sys.stdin)["data"]]'
# Expected: glm5_1_fp8
```
⚠️ Do NOT trust Level 1 alone — API can stay alive while engine is deadlocked.

**Level 2 — Engine alive (correct GLM probe):**
```bash
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
# Expected: short completion text in <10s. If timeout: engine deadlocked — need full restart.
```

**Level 3 — Full generation test:**
```bash
curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"请写一段关于人工智能发展历史的话，不少于100字","max_tokens":500,"temperature":0}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["choices"][0]["text"])'
# Check: no null content, finish_reason is "stop" or "length"
```

## 5. Pre-Startup Cleanup (Critical)

**Always run before starting** — stale processes hold GPU VRAM and will cause `ValueError: Free memory on device cuda:N` on restart:

```bash
# 1. Kill via API server PID (not enough — worker orphans remain)
pkill -9 -f 'vllm.*glm5_1_nvfp4' 2>/dev/null || true

# 2. Kill orphaned VLLM::Worker_TP* PIDs directly (invisible to ps aux, only via nvidia-smi)
#    From 70.96 session: PIDs 11417-11424 were holding 57834 MiB/gpu after API server killed
sudo kill -9 <PID> [...]

# 3. Clear Triton cache (stale PTX/JIT kernels cause shared memory errors after kernel patches)
sudo rm -rf /root/.triton/cache

# 4. Verify GPU memory released — should show ~14 MiB/gpu idle
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
```

**Full orphan check** (use this, not `ps aux`):
```bash
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader
# Expected after cleanup: no VLLM::Worker_* entries
```

## 6. Docker Container Startup (Remote)

**Production script:** `/data/model_startup_script/start_glm5_nvfp4_docker.sh`
This is a self-contained startup script with process cleanup, Triton cache clearing, container lifecycle, and polling health-check. It runs fully automated:

```bash
# On 70.96 — runs the full startup sequence automatically:
ssh jianliu@10.10.70.96 "source ~/.bashrc && sudo bash /data/model_startup_script/start_glm5_nvfp4_docker.sh"
```

**What the script does (5 steps):**
1. `pkill -9 -f 'vllm.*glm5_1_nvfp4'` + `sudo docker kill` — kills stale processes and container
2. `rm -rf /root/.triton/cache` — clears Triton cache (inside container, no sudo needed)
3. `sudo docker run -d ... --entrypoint /bin/bash $IMG -lc 'sleep infinity'` — starts container with keep-alive. **Critical detail:** `--entrypoint /bin/bash` is required so `-lc` is interpreted as `-l` (login shell) + `-c` (command string) by bash, not by Docker CLI. Without it, `sleep infinity` runs as raw CMD without a shell environment, causing path/environment issues.
4. Writes `/tmp/start_vllm.sh` inside container via `docker exec cat > heredoc`, then `docker exec -d` to start vLLM detached
5. Polls `/v1/models` every 2s for up to 180s — exits 0 on success, dumps last 20 log lines on failure

**Log:** `/data/model_startup_script/glm5_nvfp4_docker.log`

> **Note:** `jianliu` is not in the docker group — `sudo docker` is required. For non-interactive runs, confirm with user before proceeding, or add `jianliu` to docker group once: `sudo usermod -aG docker jianliu` (requires re-login).

### Running Benchmarks

**vLLM bench serve** must run via SSH to 70.96 (not from local WSL — vllm not installed locally and remote network is unreachable from WSL). Always use `HF_HUB_OFFLINE=1` + `--tokenizer /data/models/glm_5_1_nvfp4/` + `--tokenizer-mode slow` to avoid tokenizer download hangs. Benchmark script: `scripts/bench_glm5_nvfp4_prefix_cache.sh`. Full patterns: `references/vllm-bench-serve.md`.

**Engine deadlock under benchmark load**: Under heavy benchmark load (500 prompts, concurrency=64, burst), the engine can deadlock — `/v1/models` returns 200 but `/v1/completions` hangs. Fix: kill all vLLM processes, clear Triton cache, restart via startup script. See `references/vllm-bench-serve.md`.

## 7. Reasoning Effort (`reasoning_effort`)

The GLM-5.1-NVFP4 server accepts `reasoning_effort` as a request-time parameter via `/v1/chat/completions`.

**Valid values** (server-side enum — anything else returns HTTP 400):
```
'none', 'low', 'medium', 'high'
```
`max` / `xhigh` / `ultra` are NOT accepted — they return:
```
HTTP 400: Input should be 'none', 'low', 'medium' or 'high'
```
This is independent of the Hermes agent's own `reasoning_effort` config (which uses `xhigh`).

**Behavioral summary:**

| `reasoning_effort` | `reasoning` field | `content` field |
|--------------------|-------------------|-----------------|
| `none` | `null` | Final answer (no thinking) |
| `low` | Short (~100-150 chars) | Final answer — cleanest output |
| `medium` | Medium detail | Truncated if reasoning eats budget |
| `high` | Full detailed reasoning | Often `null` — reasoning consumes all tokens |

**`content: null` at `high` is expected behavior** — the model's thinking output fills the token budget. Workaround: use `low` for concise final answers, or use `/v1/completions` (non-chat) which has no `reasoning` field and returns clean text.

Full test output and server-side validation trace: `references/reasoning-effort.md`

## 7. GLM Reasoning / Thinking Behaviour (Critical for Benchmarks)

The server starts with `--reasoning-parser glm45 --tool-call-parser glm47`, which changes how responses come back:

**`/v1/chat/completions`:**
- Thinking goes into the `reasoning` field (a long internal chain-of-thought)
- `content` field is **null** — the token budget is consumed entirely by thinking
- Even with `reasoning_effort: "low"`, the model still writes reasoning to the `reasoning` field; `content` may be truncated or null

**`/v1/completions`:**
- Clean final answer in `text` field only — no reasoning field
- This is the correct endpoint for benchmarks and any time you want the actual answer without thinking overhead

**Always use `/v1/completions` for benchmarks**, not `/v1/chat/completions`. The `vllm bench serve` tool uses `--endpoint /v1/completions` for this reason.

## 8. `reasoning_effort` Parameter

Valid values (server-side validated — HTTP 400 for anything else):

| Value | Effect |
|-------|--------|
| `none` | Reasoning off, answer in `content` |
| `low` | Short reasoning (~122 tokens), `content` present |
| `medium` | Medium reasoning (~126 tokens), `content` may be truncated |
| `high` | Maximum detailed reasoning — all tokens consumed, `content: null` |
| `max` | HTTP 400 — not accepted |
| `xhigh` | HTTP 400 — not accepted |
| `ultra` | HTTP 400 — not accepted |

The highest valid level is `high`. `max`/`xhigh` are Hermes agent effort levels, not GLM model params.

## 9. Benchmark Script

Prefix-cache sweep benchmark: `references/bench_glm5_nvfp4_prefix_cache.md`

Usage:
```bash
# 3 scenarios: 0%, 40%, 80% cache hit rate
bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh

# Override rate (default: inf = burst all at once)
RATE=8 bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh

# Quick smoke test
NUM_PROMPTS=10 bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh quick
```

Config: input=2048, output=512, `--random-prefix-len` controls cache hit rate:
- 0% cache → `--random-prefix-len 0`
- 40% cache → `--random-prefix-len 819` (819/2048 ≈ 40%)
- 80% cache → `--random-prefix-len 1638` (1638/2048 ≈ 80%)

Results: `/tmp/vllm_bench_results/` locally, also on remote at same path.

## 10. Common Issues

- **Benchmark setup on 70.96**: Model confirmed at `/data/models/glm_5_1_nvfp4` (verified present). No benchmark test files for GLM on 70.96 yet — `~/work/bench_test/` is empty, `~/work/bandwidth_test/scripts/` only has `test_deepseekv4_throughput_cache.py`. To set up: create `~/work/bench_test/deepseekv4_flash/` analog directory, copy `test_deepseekv4_throughput_cache.py`, and create a `run_benchmark.sh` wrapper (use `--base-url http://localhost:8000` without trailing path — script appends `/v1/chat/completions` internally).

- **vllm-ds4-sm120 fork has no `flash_attn.ops`** — The `flash-attn-4` pip package (CUTE template engine) installs a namespace package that satisfies `find_spec("flash_attn")` but does NOT include compiled `flash_attn.ops` kernels. The fork falls back to `vllm.vllm_flash_attn.ops.triton.rotary`. If rotary operations fail with `ModuleNotFoundError: No module named 'flash_attn.ops'`, check if the fallback is correctly triggered in `vllm/model_executor/layers/rotary_embedding/common.py`.
- **Flashinfer version mismatch** — `flashinfer-jit-cache` and `flashinfer` versions can differ. Set `FLASHINFER_DISABLE_VERSION_CHECK=1` in the environment to bypass.
- **`content: null` in chat completions is expected, not an error**: With `--reasoning-parser glm45` active, the model's full chain-of-thought lands in the `reasoning` field and `content` is null because all token budget is consumed by thinking. Use `/v1/completions` (plain completion) to get clean final text. This is GLM-specific behavior, not a server error.
- **API server alive but engine deadlocked**: `/v1/models → 200 OK` but `/v1/completions` times out. `VLLM::Worker_TP*` orphan processes hold GPU memory. Kill by PID (see Section 5).
- **`ps aux` misses GPU-holding workers**: VLLM worker processes spawned as subprocesses of a killed API server can become orphans invisible to `ps aux` but visible to `nvidia-smi --query-compute-apps`. Always check both.
- **`sudo docker ps` returns permission denied**: Containers started with `sudo docker` need `sudo docker ps` to inspect them. Unprivileged `docker ps` fails silently.
- **Port 8000 already in use**: `sudo lsof -ti:8000 | xargs kill -9` before restart.
- **`HF_HUB_OFFLINE=1`**: Model files must exist locally under `/data/models/`. If model missing, `ls /data/models/glm_5_1_nvfp4/` returns empty.
- **FP8 + TP + EP block_k alignment**: On FP8 MoE models with `--enable-expert-parallel`, if `input_size_per_partition` (after EP+TP sharding) is not divisible by 128 (FP8 block_k), workers crash with `ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128`. Workaround: disable EP (`--enable-expert-parallel` without EP weight filter), or use BF16 model variant.
- **`--enable-ep-weight-filter` + FP8 + TP8 causes block_k error**: The `--enable-ep-weight-filter` flag on FP8 quantized MoE models in single-node TP8 config causes the block_k mismatch error above. The working `start_vllm_qwen.sh` on 70.88 uses DP=8 (TP=1 per rank), not TP8+EP. For single-node TP8+EP with FP8, EP must be disabled.

