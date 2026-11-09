---
name: internal-gpu-node-12-12
description: Access internal GPU node 192.168.12.12 for vLLM.
version: 0.7.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [GPU, vLLM, DeepSeek, Cluster, Internal]
---

# Internal GPU Node 192.168.12.12

Access and health-check the internal GPU server at `192.168.12.12`. This node runs **DeepSeek-V4-Flash** via vLLM on **8× NVIDIA H100 80GB** GPUs (not Blackwell/warpdrive hardware). It is the default inference backend for the Hermes session and a standalone physical server on a private subnet. Direct HTTP API access is available from the Hermes host without a jump host.

**What this skill does NOT cover:** Model deployment, vLLM startup/restart, or cluster multi-node orchestration. For those, see `devops/remote-server-management`.

See `references/hardware-and-models.md` for the full hardware inventory, confirmed negative model findings (which models do NOT exist here), and GPU usage patterns. See `references/modelscope-download-workflow.md` for downloading new models to this node via ModelScope inside the container.

## When to Use

- "Check if 192.168.12.12's vLLM is running"
- "Test the DeepSeek-V4-Flash endpoint"
- "What model is on 192.168.12.12:19258?"
- "Is the API responding on the internal node?"
- "Verify Hermes default model server health"
- "Does 192.168.12.12 have the GLM model?"

## Prerequisites

- **Network**: The host running Hermes must be reachable to `192.168.12.12` (direct L2 or routed). The vLLM HTTP API is accessible without a jump host.
- **API key**: Defined in Hermes config as `api_key: __WD_DEEPSEEKV4_FLASH__` under the `deepseekv4-flash` custom provider. That literal string is the real key — send it verbatim.
- **SSH credentials**: `jianliu` with password `!QAZ2wsx`. Password-auth only (no SSH keys configured from Hermes host). SSH keys ARE set up from jump host `10.10.68.96` — use key auth when routing through 68.96 to avoid `sshpass` overhead.
- **vLLM server**: DeepSeek-V4-Flash v0.20.0 on port `19258`. Model root: `/home/public/models/deepseekv4/`. Port `51653` (secondary instance) is dead (connection reset).

## How to Run

**HTTP health check** (no auth needed — returns 401 if server is alive):

```bash
curl -s --max-time 10 http://192.168.12.12:19258/v1/models \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__"
```

**SSH** (requires `sshpass` from Hermes host, or route through 68.96 via key auth):

```bash
# Via 68.96 (key auth, no password prompt):
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "ssh -o StrictHostKeyChecking=no jianliu@192.168.12.12 \"hostname && nvidia-smi -L\""

# Direct (requires sshpass):
sshpass -p 'qs@2024.local' ssh -o StrictHostKeyChecking=no jianliu@192.168.12.12 "hostname"
```

## Quick Reference

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `http://192.168.12.12:19258/v1/chat/completions` | Chat inference (vLLM v0.20.0) | API key |
| `http://192.168.12.12:19258/v1/models` | Model metadata + root path | API key |
| `http://192.168.12.12:19258/health` | Lightweight health check | None |
| `http://192.168.12.12:19258/version` | vLLM version string | None |
| `http://192.168.12.12:19258/metrics` | Prometheus metrics | None |
| `http://192.168.12.12:8080/` | GPU monitoring dashboard (H100) | None |
| `http://192.168.12.12:8080/data/snapshots/<date>.json` | GPU history snapshots | None |
| `http://192.168.12.12:51653/v1/...` | Secondary vLLM instance (DEAD) | — |

## Procedure

### 1. API health check (recommended first step)

Invoke through the `terminal` tool:

```bash
curl -s --max-time 10 http://192.168.12.12:19258/v1/models \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__" 2>&1
```

- **`401 Unauthorized`** means the server is alive and auth is working — the key is correct.
- **Connection refused / timeout** means the server process may be down.
- **`200 OK` with model list** means full availability.

### 2. Code-completion test

```bash
curl -s --max-time 60 http://192.168.12.12:19258/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__" \
  -d '{"model":"deepseekv4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' 2>&1
```

### 3. Check GPU model and hardware info (no auth needed)

The GPU monitoring dashboard on port 8080 exposes GPU history data without authentication:

```python
import requests, json
r = requests.get('http://192.168.12.12:8080/data/snapshots/20260718.json', timeout=5)
data = r.json()  # list of snapshots
# Each snapshot: {time, gpus: [{index, name, temp_c, util_pct, mem_used_mb, mem_total_mb, power_w, power_limit_w}]}
```

CSV at `http://192.168.12.12:8080/data/gpu_history.csv` — columns: timestamp, gpu_index, name, temp_c, util_pct, mem_used_mb, mem_total_mb, power_w, power_limit_w.

### 4. Model file inventory (via vLLM API)

The `/v1/models` endpoint returns the `root` path where the model files are stored on disk:

```bash
curl -s http://192.168.12.12:19258/v1/models \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__" \
  | python3 -c "import sys,json; [print(m['id'],m['root']) for m in json.load(sys.stdin)['data']]"
```

This reveals what model is loaded and its on-disk path (currently `/home/public/models/deepseekv4/`). Note that `/data/models/` (the path used on 10.10.68.x servers) does **not** exist on 12.12. The node only stores the one model it serves.

### 5. SSH access (shell on the node)

```bash
sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@192.168.12.12 "command"
```

Typical commands:
```bash
# GPU inventory
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

# Running vLLM processes
ps aux | grep vllm | grep -v grep
```

### 4. Streaming response inspection (confirm reasoning output)

```bash
curl -s --max-time 120 http://192.168.12.12:19258/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__" \
  -d '{"model":"deepseekv4-flash","messages":[{"role":"user","content":"Solve 47*23. Return only the number."}],"max_tokens":512,"stream":true,"stream_options":{"include_usage":true}}' 2>&1 | grep '"delta"' | head -20
```

Note: DeepSeek-V4-Flash on this server does **not** produce a separate `reasoning_content` field. Thinking may be embedded inline in `content` (not guaranteed).

## Pitfalls

- **`sshpass` must be installed** on the Hermes host: `sudo apt-get install -y sshpass`. Without it, interactive SSH is blocked.
- **The server is NOT on the 10.10.68.x subnet.** Do not confuse it with 68.96's RDMA address (which uses `192.168.66.x`).
- **API key is literal.** The string `__WD_DEEPSEEKV4_FLASH__` must be sent verbatim — it is not a shell variable or placeholder.
- **SSH password `!QAZ2wsx`** — if this stops working, try via jump host `10.10.68.96` (which has `sshpass` 1.09 pre-installed) to debug.
- **DeepSeek-V4-Flash returns `reasoning: null`.** The vLLM instance does not produce structured reasoning output, even when `chat_template_kwargs: {thinking: true}` is sent.
- **Port 51653 is dead** (connection reset). Only port 19258 is active.
- **`dkexec` alias does NOT exist** on 12.12. `.bash_alias` is absent. Always use `docker exec` directly: `docker exec jianliu_sw2_public_19255 bash -c '...'`.
- **SSH to 12.12 produces conda errors from the HOST login shell** — miniconda3 activation is broken in the host's shell init, producing TypeErrors on every SSH. The `-T` flag bypasses PTY allocation and the broken host init, giving clean container output. **Always use `ssh -T`** for commands where you need clean stdout. Without `-T`, SSH output is buried under conda exception spam.
- **`modelscope` binary path** is `/opt/conda/envs/sw2_public/bin/modelscope`. It is NOT in the default PATH inside the container. Always invoke via full path.
- **`modelscope download` has NO `--force` flag** — the CLI error `unrecognized arguments: --force` is the indicator. Omit `--force`; auto-resume works without it.
- **ModelScope download monitoring** — files land directly in the target dir (no `._____temp/` staging). Key commands:
- Session detail: see `references/deepseekv4-flash-0731-download.md`
- Persistent lessons (SSH buffering, process pile-up root cause, staggered checks, pkill vs targeted kill): see `references/modelscope-download-persistent-lessons.md`

```bash
# Shard progress: count completed safetensors vs expected (48 for V4-Flash-0731)
ssh -T jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# Total size growing
ssh -T jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/'"

# Process alive
ssh -T jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep modelscope | grep -v grep'"
```

**Resume pattern**: On SSH drop mid-download, re-run the exact same command. modelscope auto-resumes. Check shard count first to find where it left off.

**⚠️ Multiple-process pile-up (CRITICAL)**: Every SSH drop/timeout spawns a new `modelscope download` process on the server. Multiple processes compete for bandwidth and make shard counting unreliable. Before restarting after a drop, always:
  1. Check running processes: `ssh -T jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep modelscope | grep -v grep'"`
  2. If count > 1, kill ALL old ones by PIDs (check via `ps aux` output), then start fresh. Pattern: identify newest PID by `ps` start time → keep it → kill all others.
  3. Newer PIDs from recent `docker exec` calls have later timestamps; older zombie PIDs have earlier timestamps.
  4. Commands for quick state checks:

```bash
# 1. Check disk progress (safetensor shard count)
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/; ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# 2. Check running process count + PIDs
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep modelscope | grep -v grep'"

# 3. Kill all modelscope processes (cleanup before restart)
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'pkill -f modelscope download'"

# 4. Start fresh download
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && /opt/conda/envs/sw2_public/bin/modelscope download --model deepseek-ai/DeepSeek-V4-Flash-0731 --local_dir /home/public/models/deepseekv4-flash-0731/ --max-workers 8 2>&1'"
```

**Download state history** (DeepSeek-V4-Flash-0731 to 12.12):
  - 88GB / 46 shards after first run
  - 96GB / 46 after second SSH reconnect
  - 100GB / 46 after kill-old cleanup
  - 103GB / 46 after third reconnect
  - 116GB / 46 shards (SSH overload, staggered checks running)
  - Expected: 48 shards, ~159GB total

**Typical model**: DeepSeek-V4-Flash-0731 = 48 safetensor shards, ~158GB total (~3.3GB/shard). Speeds vary 100 kB/s–43 MB/s across parallel workers.

- **GLM-5.2-NVFP4 copy to local disk** — transfer completed (7/18). Model now at `/mnt/data3/public/models/glm5_2_nvfp4/` (433 GB, 47/47 shards, owned by jianliu). The NFS at `/h100_nas/glm_transfer/` is the source (same 433 GB). Active rsync processes seen on 12.12 belong to other users (yirongpan, luojie), not the GLM copy.
- **No vLLM Docker images** are available on 12.12 (only `ghcr.io/openlit/openlit:latest` exists). To deploy the sparse+b12x GLM-5.2 server container (image `voipmonitor/vllm:fathomless-firmament-v16-vllm8f86f42-b12xfe06f49-fi801d57a-cu132-20260714`), you must transfer it from 68.96 first. See `devops/remote-server-management` → "Save → Split → HTTP Server → Screen" for the proven method. As of 2026-07-23, image is 12 GB compressed (48.4 GB raw, ~4:1 pigz ratio), split into 23×500MB chunks at `/data/glm52_b12x_img.tar.gz.chunk_*` on 68.96, with HTTP server at 18999. A screen session `imgdl` on 12.12 was initiated to download chunks via wget and load into docker — check with `screen -r imgdl`.
- **Direct network between 68.96 ↔ 12.12 is only 10 Mbps** with heavy packet loss (980 retransmits/10s, iPerf3 confirmed). Do NOT use direct rsync or SCP between these hosts. Use the shared NAS at `/mnt/nas_h100/` (on 68.96) or `/h100_nas/` (on 12.12) as an intermediary — it achieves 36-600 MB/s write speeds.
- **SSH key auth now set up** between 68.96 (jianliu@oem96) → 12.12 (jianliu@h100-SYS-821GE-TNHR). No `sshpass` needed when routing through 68.96.
- **This is an H100 server**, not Blackwell/warpdrive hardware. No nvidia-smi stub issue, no wd-smi needed. Standard nvidia-smi works.
- **vLLM `/v1/models` root field** reveals the on-disk model path — use it for inventory instead of SSH.
- **vLLM `/v1/models` root field** reveals the on-disk model path — use it for inventory instead of SSH.

## Model Inventory (2026-08-02)

| Model | Path | Size | Shards | Status |
|-------|------|------|--------|--------|
| deepseekv4-flash | `/home/public/models/deepseekv4/` | ~158GB | 48 | ✅ Serving on 19258 |
| DeepSeek-V4-Flash-0731 | `/home/public/models/deepseekv4-flash-0731/` | ~159GB | 48 | Downloading (in progress, ~116GB/46 shards as of 2026-08-03, ~43GB remaining, ~2 shards left) |

## Verification

Run this to confirm the server is alive and the API is functional:

```bash
curl -s --max-time 15 http://192.168.12.12:19258/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer __WD_DEEPSEEKV4_FLASH__" \
  -d '{"model":"deepseekv4-flash","messages":[{"role":"user","content":"Return only the number: 7+5"}],"max_tokens":10}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'choices' in d else 'FAIL')"
```

Expected output: `OK` (when the server is healthy and the API key is correct).
