---
name: remote-server-70-96
description: Remote GPU server management for 10.10.70.96 (oem96) — 8× NVIDIA RTX PRO 6000 Blackwell Server Edition (96GB each), DeepSeek-V4-Pro master node, RoCE v2 bond0, LVM storage, proxy access, SSH and operations.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Remote Server 10.10.70.96 — NVIDIA RTX PRO 6000 Blackwell Server Edition

## Access

```bash
ssh jianliu@10.10.70.96
```

| Field | Value |
|-------|-------|
| **Username** | jianliu |
| **IP (management)** | 10.10.70.96 |
| **IP (100G RDMA)** | 192.168.66.10/24 on `bond0` (LACP) — **NOT** 10.10.71.96 (doesn't exist) |
| **Password** | !QAZ2wsx |
| **Sudo Password** | !QAZ2wsx (same as login) |

> **Important:** This server has a proxy (`http://10.10.60.140:7890`) configured in `~/.bashrc`. Non-interactive SSH does NOT load `.bashrc` automatically. **Always prefix remote commands with `source ~/.bashrc &&`**.

### SSH Patterns

```bash
# Non-interactive command (most common)
ssh jianliu@10.10.70.96 "source ~/.bashrc && command"

# Sudo commands — use SUDO_ASKPASS helper (sudo -S piped password is blocked)
ssh jianliu@10.10.70.88 'cat > /tmp/spwd_helper.sh << '\''EOF'\''
#!/bin/bash
echo "!QAZ2wsx"
EOF
chmod 700 /tmp/spwd_helper.sh
SUDO_ASKPASS=/tmp/spwd_helper.sh sudo -A <command>; rm -f /tmp/spwd_helper.sh'

# SCP / file transfer
scp local_file jianliu@10.10.70.96:/path/to/dest/

# Long-running background process — USE setsid, NOT nohup ... &
# The pattern "ssh host 'nohup cmd > log 2>&1 &'" causes the process to die silently
# within minutes because SSH ends the session immediately after nohup spawns its child.
# setsid creates a new session so the process survives SSH disconnection.
ssh jianliu@10.10.70.96 "source ~/.bashrc && \
  setsid env VAR=value /path/to/command \
    </dev/null >/dev/null 2>&1"
# </dev/null >/dev/null is critical: setsid needs detached stdin/stdout/stderr.
# Verify: ssh host "pgrep -fa 'command'"  # check the process is alive after 30s.

# Writing Python/shell files to remote server — heredoc escaping breaks reliably.
# Use base64 encoding to transfer content losslessly:
# 1. Encode locally
python3 -c "import base64; open('/tmp/script_b64.txt','w').write(base64.b64encode(open('/tmp/script.py').read()).decode())"
# 2. Decode on remote (quotes protect all special chars)
B64=$(cat /tmp/script_b64.txt) && ssh jianliu@10.10.70.88 "echo '$B64' | base64 -d > /path/to/script.py"
# 3. Verify syntax
ssh jianliu@10.10.70.88 "python3 -m py_compile /path/to/script.py && echo syntax_ok"
# Works for any binary content too (images, zip, etc.)
```
```

## Hardware Specs

| Component | Detail |
|-----------|--------|
| **Hostname** | oem96 |
| **IP (management)** | 10.10.70.96 on `ens20f0` (Intel I350 1GbE) |
| **IP (high-speed RDMA)** | 192.168.66.10/24 on `bond0` (LACP, RoCE v2) — NOT 10.10.71.96 (doesn't exist on any interface) |
| **GPU** | 8× NVIDIA RTX PRO 6000 Blackwell Server Edition |
| **GPU Memory** | 97,887 MiB (~96 GB) each (768 GB total) |
| **Compute Capability** | 12.0 (Blackwell) |
| **Driver** | 595.58.03 |
| **CUDA Driver** | 13.2 |
| **CPU** | 2× Intel Xeon (2 NUMA domains) |
| **NUMA0** | GPU0-3, CPU cores 0-31,64-95 |
| **NUMA1** | GPU4-7, NIC0 (rocep200s0f0), CPU cores 32-63,96-127 |
| **System** | Ubuntu 22.04.1 LTS, Kernel 5.15.0-43-generic |
| **Storage (root)** | 1.7 TB LVM — `/dev/mapper/vgubuntu-root` |
| **Storage (data)** | LVM, mounted at `/data` |
| **Proxy** | `http://10.10.60.140:7890` (via `~/.bashrc`) |

## Current Service Status (as of 2026-06-03)

### GLM-5.1-FP8 vLLM Server (PP=2 master) ✅ ACTIVE

**Model:** `glm5_1_fp8` (GLM-5.1-FP8, served as `glm5_1_fp8`)
**Config:** TP=8, PP=2, FP8 kv-cache, TRITON_MLA + enforce_eager, max_len=65536
**PID:** 329710 (APIServer), with PP worker subprocesses
**Endpoint:** `http://10.10.70.96:8000/v1/models`
**GPU memory:** 74,764 MiB / 97,887 MiB per card (~76%)
**Workers per card:** ~0% GPU util (idle, no active requests)
**Log:** `/tmp/vllm_glm5_master.log`

To verify:
```bash
curl -s http://10.10.70.96:8000/v1/models | python3 -c 'import sys,json; [print(m["id"]) for m in json.load(sys.stdin)["data"]]'
```

### GLM-5.1-NVFP4 vLLM Server ✅ ACTIVE (2026-06-08, restarted after benchmark deadlock)

**Model:** `glm5_1_nvfp4` (NVIDIA GLM-5.1-NVFP4, served as `glm5_1_fp8`)
**Startup:** Production script `/data/model_startup_script/start_glm5_nvfp4_docker.sh` (Docker container, self-contained with process cleanup + health-check polling)
**Container:** `glm5_nvfp4_vllm`, image `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412`
**API server PID:** 30329 (root), 8× VLLM::Worker_TP*DCP* (PID 31081-31088)
**Endpoint:** `http://10.10.70.96:8000/v1/models`
**GPU memory:** ~87,117 MiB/card (~89%) — no GPU util (idle, no active requests)
**Log:** `/data/model_startup_script/glm5_nvfp4_docker.log`
**Benchmark script:** `/home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh`

> **Benchmark deadlock pattern (confirmed 2026-06-08):** Under heavy benchmark load (500 prompts, concurrency=64), the engine deadlocks — `/v1/models` returns 200 but `/v1/completions` hangs. GPU stays at ~97% util with zero throughput. Pre-bench engine check is REQUIRED:
> ```bash
> timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
>   -H "Content-Type: application/json" \
>   -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
> ```
> If this times out → engine deadlocked → full restart before benchmarking.
> Key script fixes (2026-06-08): `--backend openai` (not `openai-chat`), `--num-warmups 0` (warmup request deadlocks engine under load), `--save-detailed`, `--tokenizer /data/models/glm_5_1_nvfp4/` + `HF_HUB_OFFLINE=1`. See `glm5-nvfp4-vllm-server` skill `references/bench_glm5_nvfp4_prefix_cache_fixes.md` for full command block.

Health check (always probe engine, not just API):
```bash
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
```
Health check (always probe engine, not just API):
```bash
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":32,"temperature":0}'
```

Full benchmark details: `references/glm5-nvfp4-bench.md`
**Full model config:** See `references/glm5-nvfp4-model-config.md`

### GLM-5.1-NVFP4 Download

**Total:** 49 shards, expected ~434 GB
**Last seen (2026-06-03 ~17:00 CST):** 23/49 shards, 224 GB — download still in progress
**Speed:** ~5-6 GB / 5 min (~20 MB/s via hf-mirror.com)

> **Status (2026-06-03):** Download NOT yet complete. Original HF download process exited after completing 23 shards. Active locks on shards 24-31 suggest download may have restarted via HF cache system. If locks are stale (>30 min old), kill and restart:
> ```bash
> ssh jianliu@10.10.70.96 "pkill -f 'hf download nvidia/GLM-5.1-NVFP4'"
> # Then restart per pattern in Download HF Models section above
> ```

**Shards 46-49:** 3.6-5 GB each (lm_head/embed, normal for these final shards)
**HF_TOKEN:** Not required — CAS worked anonymously via hf-mirror.com
**Duration:** ~6 hours over 4 restarts (~2-3 hours per run before CAS URL expiry)

**Restart pattern on CAS expiry:**
```bash
# 1. Kill all hf download processes:
ssh jianliu@10.10.70.96 "pkill -f 'hf download nvidia/GLM-5.1-NVFP4'"
# 2. Clean stale cache:
ssh jianliu@10.10.70.96 "rm -rf /data/models/glm_5_1_nvfp4/.cache/huggingface/"
# 3. Restart (use setsid, NOT nohup ... &):
ssh jianliu@10.10.70.96 "source ~/.bashrc && setsid env HF_ENDPOINT=https://hf-mirror.com \
  /data/venvs/vllm-ds4/bin/hf download nvidia/GLM-5.1-NVFP4 \
  --local-dir /data/models/glm_5_1_nvfp4 --repo-type model --max-workers 2 \
  </dev/null >/dev/null 2>&1"
```

Monitor with:
```bash
ssh jianliu@10.10.70.96 "find /data/models/glm_5_1_nvfp4 -maxdepth 1 -name 'model-*.safetensors' | wc -l && du -sh /data/models/glm_5_1_nvfp4/"
```

**Full session log:** See `references/70-96-models.md` for complete progress timeline.
```

## GPU Topology

Each GPU sits behind its own PCIe bridge (Intel 352a, rev 30). Both the GPU device itself and the upstream bridge support **Gen5 (32.0 GT/s)** . Under load, the link negotiates at **Gen5 ×16 (32 GT/s)** — confirmed by both `nvidia-smi` and sysfs on all 8 GPUs simultaneously when all GPUs are in P0 performance state.

| GPU | Bus Address | PCIe Bridge | Negotiated (idle) | Negotiated (load) | Max Capable |
|-----|-------------|-------------|:----------------:|:-----------------:|:-----------:|
| 0 | 16:00.0 | 15:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 1 | 27:00.0 | 26:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 2 | 38:00.0 | 37:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 3 | 5A:00.0 | 59:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 4 | 98:00.0 | 97:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 5 | A8:00.0 | A7:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 6 | B8:00.0 | B7:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |
| 7 | D8:00.0 | D7:01.0 | Gen1 ×16 | **Gen5 ×16** | Gen5 |

**Key insight — PCIe downclock on idle:** The GPUs are NOT locked at Gen1. When idle (Performance State P8), the GPU **power-gates the PCIe link** and renegotiates down to Gen1 (2.5 GT/s) for power saving. Under any workload (P0 state), all 8 GPUs simultaneously renegotiate to **Gen5 ×16 (32.0 GT/s, ~63 GB/s bidirectional)** — confirmed by both `nvidia-smi` and sysfs.

The only bottleneck for 8-card collectives is the **cross-NUMA QPI/UPI interconnect** (SYS) — GPU0-3 (NUMA0) traversal to GPU4-7 (NUMA1) caps aggregate BusBW at ~39-40 GB/s even with Gen5 ×16 per GPU pair.

**NCCL benchmark results at PCIe Gen5 (P0, 2026-05-28):**
| Operation | Peak AlgoBW | Peak BusBW | Avg BusBW | Latency @ 8B |
|-----------|:----------:|:----------:|:---------:|:----------:|
| all_gather | **42.66 GB/s** | 37.33 GB/s | 14.92 GB/s | 34.52 us |
| broadcast | **40.13 GB/s** | **40.13 GB/s** | 17.08 GB/s | 34.23 us |
| all_reduce | 22.45 GB/s | **39.30 GB/s** | 16.03 GB/s | 34.67 us |
| reduce_scatter | 26.87 GB/s | 23.51 GB/s | 10.60 GB/s | 35.14 us |
| sendrecv | 24.95 GB/s | 24.95 GB/s | 10.76 GB/s | 34.12 us |
| alltoall | 15.56 GB/s | 13.62 GB/s | 6.28 GB/s | 48.42 us |

**PCI bus hierarchy** — root bus `0000:00` → Intel host bridges → per-GPU PCIe bridges (Intel 352a) → GPU:
```bash
lspci -t | grep '15\]-\|26\]-\|37\]-\|59\]-\|97\]-\|a7\]-\|b7\]-\|d7\]-'
```

### Network Interfaces

| Interface | Hardware | Speed | IP | Purpose |
|-----------|----------|-------|----|---------|
| ens20f0 | Intel I350 (igb) | 1 Gb/s | 10.10.70.96 | Management, SSH |
| ens35f0np0 | ConnectX-6 Dx (mlx5) | 100 Gb/s | — (bond0 slave) | RDMA/NCCL via bond0 |
| ens35f1np1 | ConnectX-6 Dx (mlx5) | 100 Gb/s | — | Unused (no cable) |
| bond0 | LACP bond (ens35f0np0) | 100 Gb/s | 192.168.66.10/24 | RDMA RoCE v2, NCCL inter-node |

**Important:** `ens35f0np0` is a **slave in a LACP bond0** (802.3ad dynamic link aggregation), not a standalone interface. The effective RDMA IP is **192.168.66.10/24** on `bond0`, **not** 10.10.71.96 (that IP was never configured). RDMA device: `rocep200s0f0/1` — state ACTIVE, LINK_UP, MTU 9000.

The bond0 + ensemble arrangement is persisted via NetworkManager.

## Role: DeepSeek-V4-Pro Master Node (PP=2 Multi-Node) & GLM-5.1-FP8 Master Node

### GLM-5.1-FP8

**Startup script:** `/data/venvs/vllm-ds4/start_glm5_fp8_2node.sh`

**Note:** GLM-5.1-FP8 (GlmMoeDsaForCausalLM, 704 GB FP8, 256 experts) requires transformers >= 5.4.0 and CC 12.0 MLA patches. See `references/glm5-fp8-deployment.md` under the `remote-server-management` skill for full setup instructions. Known issues: sparse MLA not working on Blackwell, FlashInfer TRT-LLM kernel has XQA head count mismatch with GLM's 64-head config.

### PP=2 Startup Configuration

Both strategies have been tested. **PP=2 (Pipeline Parallelism) is the recommended strategy** — it outperforms DP=2 across all metrics:

| Metric | DP=2 | PP=2 | PP Advantage |
|--------|------|------|-------------|
| Short prompt TTFT (S1) | 2.6s | **2.2s** | 15% faster |
| Long prompt TTFT (S2) | 260.5s | **186.7s** | 28% faster |
| Prefix cache TTFT (S3) | 142.8s | **43.2s** | 3.3× faster |
| Prefix throughput | 4.14 tok/s | **7.73 tok/s** | 87% more |

### Startup Scripts

**PP=2 (recommended):** `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh`
```bash
# Master (70.96):
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh master
# Worker (70.98):
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh worker
```

**DP=2 (alternative):** `/data/venvs/vllm-ds4/start_dsv4_pro_tp8_dp2_ep.sh`

### Architecture Comparison

**PP=2 (Pipeline Parallelism):**
- Model layers split across nodes — each node holds ~half the layers
- All GPUs participate in every request (both nodes work on prefill+decode in pipeline)
- Cross-node communication via NCCL (TP group spans both nodes)
- No DP coordinator handshake overhead
- Best for: prefix cache workloads, long prompts, balanced throughput

**DP=2 (Data Parallelism):**
- Each node holds full model weights sharded by TP+EP
- Different requests processed in parallel on each node
- DP coordinator does ZMQ handshake for every batch, adding latency
- More KV cache pressure (each node needs full model + KV cache)
- **DP handshake can fail** — 5-minute timeout with "Did not receive response from front-end process"

### PP=2 Startup Configuration

The proven PP=2 startup script (`start_dsv4_pro_2node.sh`) has been fixed to use the **actual** RDMA IPs (192.168.66.x) and correct interface names. Key configuration:

```bash
export NCCL_SOCKET_IFNAME=bond0       # MUST be bond0 (not ens35f0np0 — no IP)
export GLOO_SOCKET_IFNAME=bond0       # same: GLOO needs an interface with IP
export TP_SOCKET_IFNAME=bond0
export VLLM_HOST_IP="192.168.66.10"   # master; worker uses 192.168.66.20
export MASTER_ADDR="192.168.66.10"    # head node for TCPStore
export NCCL_IB_DISABLE=0
export NCCL_IB_HCA=$(rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,')  # auto-detect: rocep200s0f0 on 96, mlx5_bond_0 on 98
export NCCL_IB_GID_INDEX=3
export NCCL_IB_TIMEOUT=23
export NCCL_IB_QPS_PER_CONNECTION=4
export NCCL_IB_TC=136
export NCCL_CROSS_NIC=0
export NCCL_ALGO=Ring
export NCCL_MIN_NCHANNELS=8
export NCCL_NET=IB
```

**Key fixes from original script:**
- `NCCL_SOCKET_IFNAME` was `ens35f0np0` (bond slave with NO IP) → changed to `bond0` (has 192.168.66.x)
- `GLOO_SOCKET_IFNAME` same fix — GLOO crashes with `Unable to find address for: ens35f0np0`
- `HEAD_IP` was `10.10.71.96` (non-existent) → changed to `192.168.66.10`
- `NCCL_IB_HCA` was hardcoded to `rocep200s0f0` → now auto-detected per node (70.96 has `rocep200s0f0`, 70.98 has `mlx5_bond_0`)
- Removed `--api-key ***` (literal asterisks that would fail to parse)

### GLM-5.1-FP8 Startup Script (Critical Fix)

**Startup script:** `/data/model_startup_script/start_glm5_fp8_2node.sh` (not in vllm-ds4 directory — the vllm-ds4 directory only holds startup scripts for DeepSeek models)

**Critical: Full 3-step cleanup before restart** (after any crash or kernel code patch — must run on ALL nodes):
```bash
ssh jianliu@10.10.70.<NODE> "pkill -9 -f vllm; fuser -k <PORT>/tcp; rm -rf /root/.triton/cache"
```
Skipping `rm -rf /root/.triton/cache` causes patched Triton kernels to still fail with `OutOfResources: shared memory` — the GPU holds stale PTX from the old compiled kernel.

See `references/glm5-fp8-debug-2026-06-03.md` for full debugging workflow.

See the `mla-blackwell` skill for full debugging workflow. Summary of known issues:

1. **Wrong venv sourced** — The script at `/data/model_startup_script/start_glm5_fp8_2node.sh` has been seen with `vllm-latest-cu130` instead of `vllm-ds4`. Always verify before starting:
```bash
grep activate /data/model_startup_script/start_glm5_fp8_2node.sh
# Must show: source /data/venvs/vllm-ds4/bin/activate
```

2. **FlashInfer MLA block_tables ndim=3** — After fixing the venv, the `flashinfer_mla_sparse.py` patch (see `mla-blackwell` skill) may also be needed for first-inference success.

Full details in `references/glm5-fp8-debug-2026-06-03.md` and the `mla-blackwell` skill.

### Known Startup Issues

- **FlashInfer MLA block_tables ndim=3** (2026-06-03): `flashinfer_mla_sparse.py` line 358 has `.unsqueeze(1)` that creates a 3D tensor where FlashInfer 0.6.8.post1 expects 2D. See `mla-blackwell` skill for fix and debug workflow.

- **EADDRINUSE (port 29505 / ephemeral ports)**:

- **FlashInfer MLA block_tables ndim=3** (2026-06-03): `flashinfer_mla_sparse.py` line 358 has `.unsqueeze(1)` that creates a 3D tensor where FlashInfer 0.6.8.post1 expects 2D. See `mla-blackwell` skill for fix and debug workflow.

- **Full cleanup before restart (critical after crashes/patches):** When restarting after a crash or after patching GPU kernel code (Triton MLA kernels, FlashInfer, etc.), all three must be done together on every node:
  ```bash
  # On EACH node (master AND worker):
  ssh jianliu@10.10.70.<NODE> "pkill -9 -f vllm; fuser -k <PORT>/tcp; rm -rf /root/.triton/cache"
  ```
  - `pkill -9 -f vllm` — kills stale `VLLM::Worker_PP*` / `VLLM::EngineCore` processes holding GPU VRAM
  - `fuser -k <PORT>/tcp` — releases stuck TCPStore/ZMQ ports (`29505`, `29507`, ephemeral)
  - `rm -rf /root/.triton/cache` — **clears stale PTX/JIT kernels** from GPU VRAM. This is the most commonly forgotten step. Without it, patched Triton kernels (e.g. `num_stages=2` → `1`) may still fail with `OutOfResources: shared memory` because the GPU holds the old compiled kernel with the old shared memory requirement.

- **EADDRINUSE (port 29505 / ephemeral ports)**: Leftover VLLM::Worker processes from failed starts hold the TCPStore port AND random ephemeral ZMQ ports (e.g., addr='tcp://192.168.66.10:48895'). ZMQ's `Cannot assign requested address` or `Address already in use` on ephemeral ports means TIME_WAIT hasn't expired. Fix: `MASTER_PORT=29507` (increment on each restart) or wait 60s for TIME_WAIT to clear. Always verify with `ss -tlnp | grep 295` and kill all stale VLLM::Worker PIDs before restarting.
- **GLOO socket ifname**: If `GLOO_SOCKET_IFNAME` points to an interface without an IP, the worker crashes with `Unable to find address for: <ifname>`. Always use `bond0` (has the RDMA IP).
- **RDMA device name differs per node**: 70.96 uses `rocep200s0f0`, 70.98 uses `mlx5_bond_0`. The NCCL_IB_HCA must match. Auto-detect with `rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,'`.
- **Start order**: Worker first → wait ~10s for TCPStore → then master. The worker waits for the master's TCPStore; starting master first can cause ZMQ `Cannot assign requested address` if the worker-side VLLM_HOST_IP binding isn't ready.

- **PP=2 cluster crash: Master too slow to initialize (2026-06-03)** — Worker successfully connects to master TCPStore (ranks 8-15 log in) but if the master's vLLM engine takes >5 minutes to fully load (model loading, KVCache profiling, NCCL init), the worker's ProcessGroupNCCL heartbeat monitor loses contact with the master's TCPStore and crashes with:
  ```
  TCPStore.cpp:106 sendBytes failed: Broken pipe
  ProcessGroupNCCL.cpp:1826 [rank N] Failed to check "should dump" flag on TCPStore
  (TCPStore server has shut down too early)
  ```
  **Symptoms:** Both master (70.96) and worker (70.98) are up and running at different times, but worker dies ~5 min after model loading starts on master. Master serves requests normally, worker holds GPU memory but isn't distributed-init'd.

  **Fix:** Time the startup so worker doesn't start until master is FULLY loaded (APIServer running, all ranks confirmed). A safer pattern: start master → wait for its `INFO: Application startup complete` in log → then start worker.

  **Diagnostic:**
  ```bash
  # Master: wait for this line in log before starting worker
  ssh jianliu@10.10.70.96 "grep 'Application startup complete' /tmp/vllm_glm5_master.log"
  # Worker: check rank connections
  ssh jianliu@10.10.70.98 "grep 'rank=' /tmp/vllm_glm5_worker.log | tail -5"
  # Worker: check if still alive
  ssh jianliu@10.10.70.98 "ps aux | grep vllm | grep -v grep"
  ```

### Startup Order (Important)

1. Start the **worker** first
2. Wait ~30-45 seconds for model init
3. Start the **master**

Starting the master first causes a ZMQ `Cannot assign requested address` error because the worker-side `VLLM_HOST_IP` binding isn't ready yet.

### NCCL Version Requirement

Blackwell (compute capability 12.0) requires **NCCL ≥ 2.30**. The torch-bundled NCCL 2.28.9 fails with:
- `NCCL error: invalid usage` during `ncclCommInitRank`
- `NCCL error: unhandled system error` during `ncclAllReduce`

**Fix:** Copy the system NCCL 2.30.4 into the venv:
```bash
cp /usr/lib/x86_64-linux-gnu/libnccl.so.2.30.4 \
  /data/venvs/vllm-ds4/lib/python3.12/site-packages/nvidia/nccl/lib/libnccl.so.2
```
(Note: this may cause pynccl_wrapper API incompatibility. The working config was on the original torch-bundled NCCL with proper GPU reset.)

### PP=2 Startup Order

1. Start **worker** (70.98) first — it waits for master's TCPStore
2. Wait ~45 seconds
3. Start **master** (70.96)

### Diagnostic: Checking if the cluster is alive

The worker node (70.98) will NOT respond to `curl localhost:8000` — this is by design:

1. **Check master's health:**
   ```bash
   curl -s http://localhost:8000/health
   ```

2. **Verify with real inference (master node) — short prompt first:**
   ```bash
   # Start with few tokens to check responsiveness
   curl -s -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek_v4_pro","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
   ```
   
   If the first request times out (common during warmup / first inference), try again with a short prompt — the server may be working fine but the first request can be slow due to Triton JIT compilation.

3. **Full response test (100 tokens):**
   ```bash
   curl -s -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek_v4_pro","messages":[{"role":"user","content":"hi"}],"max_tokens":100}' | python3 -m json.tool
   ```

4. **Check worker's process health (from the worker):**
   ```bash
   ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker'
   ```

5. **Check master's logs for successful inference:**
   ```bash
   tail -f /tmp/vllm*.log | grep "200 OK"
   ```

6. **Check GPU utilization on both nodes:**
   ```bash
   nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader
   ```

### Current Configuration (as of 2026-05-27)

The recommended production configuration for DeepSeek V4 Pro with PP=2:

```bash
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh master
```

This script uses:
- TP=8 + PP=2 + EP=8
- max-num-seqs=512, max-num-batched-tokens=8192  
- max-model-len=1,048,576, gpu-memory-utilization=0.92
- compilation mode=3, cudagraph=FULL_AND_PIECEWISE
- RoCE v2 (ConnectX-6, 100GbE) via ens35f0np0

> **Note:** `--no-enable-flashinfer-autotune` is irrelevant for DeepSeek V4 which uses MLA (Multi-Head Latent Attention) with a custom Triton backend — FlashInfer autotune has no effect on this model.

### Log Redirection (IMPORTANT)

The current startup script redirects vLLM output directly to a log file — **not** through `tee`:

```bash
vllm serve ... > "$LOG_FILE" 2>&1
```

This avoids a critical failure mode: if the `tee` process dies (OOM, disk pressure, log rotation), the pipe breaks and vLLM receives SIGPIPE, killing the entire server. Direct file redirection (`>`) has no intermediate process, so nothing can kill vLLM.

The log file pattern is `/tmp/vllm_tp8_dp2_$$.log` (where `$$` is the bash PID at launch time).

### API

**Endpoint:** `http://10.10.70.96:8000`
**Model name:** `deepseek_v4_pro`
**API key:** `sk-warpdriveai`

## vLLM Engine Health Check (Critical Pattern)

**DO NOT trust `/v1/models` for engine aliveness.** The API server process can stay alive while the engine core is deadlocked. The engine crash pattern:

```
# /v1/models → 200 OK (API layer alive)
# /v1/completions → hangs / times out (engine deadlocked)
# GPU util stays at ~100% but does nothing (empty compute loop)
```

**Root cause signatures** (from `/tmp/vllm_*.log`):
```
RuntimeError: Worker failed with error '[/pytorch/third_party/gloo/gloo/transport/tcp/pair.cc:547]
  Connection closed by peer [192.168.66.x]:<port>'
EngineCore encountered a fatal error.
vllm.v1.engine.exceptions.EngineDeadError: EngineCore encountered an issue.
```

This is a Gloo/NCCL inter-process communication failure — the EngineCore worker dies, causing the entire inference engine to deadlock. The API server process stays up but can't serve requests.

**Proper engine health check — ALWAYS use this, not just `/v1/models`:**
```bash
# Quick 32-token probe — times out at 30s if engine is dead
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<served_model_name>","prompt":"hi","max_tokens":32,"temperature":0}'
# Expected: a short completion in <10s
# If timeout: engine is deadlocked — need full restart
```

**What to check when engine seems stuck:**
```bash
# 1. API layer alive?
curl -s http://localhost:8000/v1/models | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"

# 2. Engine alive? (the real check)
timeout 30 curl -s -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<served_model_name>","prompt":"hi","max_tokens":16,"temperature":0}'

# 3. GPU actually working?
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used --format=csv,noheader

# 4. Engine log — look for "EngineCore" fatal errors
tail -30 /tmp/vllm*.log | grep -E 'ERROR|EngineDead|Connection closed|Worker died'

# 5. Process list — is EngineCore worker alive?
ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker_TP' | grep -v grep
```

**Restart procedure after engine deadlock:**
```bash
# Kill API server (pid of python3 -m vllm.entrypoints.openai.api_server):
sudo kill <api_server_pid>
sleep 5
# Clear stale Triton kernels (CRITICAL after any crash):
sudo rm -rf /root/.triton/cache
# Verify all GPU memory released:
nvidia-smi --query-gpu=memory.used --format=csv,noheader
# Then restart server per its startup script
```

## vLLM Environment

- Source: `/data/vllm-ds4-sm120/`
- Venv: `/data/venvs/vllm-ds4/` (Python 3.12, PyTorch 2.11.0+cu130)
- CUDA dev packages installed

## Quick Health Check

```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && \
  echo '=== GPU ==='; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1; \
  echo '=== CUDA Driver ==='; nvidia-smi -q | grep 'CUDA Version'; \
  echo '=== Memory ==='; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader; \
  echo '=== Disk ==='; df -h / /data | tail -2"
```

## Batch Operations (cluster)

Part of 93/95/96 cluster — use bulk commands:

```bash
for h in 93 95 96; do
  echo "=== 10.10.70.$h ==="
  ssh jianliu@10.10.70.$h "source ~/.bashrc && command"
done
```

## Download HF Models (via hf-mirror.com)

The `hf` CLI is in the `vllm-ds4` venv — not globally installed. Use this sequence:

```bash
# 1. Verify mirror reachability (huggingface.co direct may time out; hf-mirror.com works)
ssh jianliu@10.10.70.96 "source ~/.bashrc && curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://hf-mirror.com"
# Expected: 200

# 2. Check what's already downloaded
ssh jianliu@10.10.70.96 "find /data/models/<model> -maxdepth 1 -name 'model-*.safetensors' | wc -l"

# 3. Start background download — USE setsid, NOT nohup ... &
# hf download auto-resumes from cache (.incomplete files are reused, only missing bytes fetched).
# No --resume-download flag — this doesn't exist in hf CLI v1.17.0.
# Using max_workers=2 (default 8 causes silent death on large files).
ssh jianliu@10.10.70.96 "source ~/.bashrc && mkdir -p /data/models/<model> && \
  setsid env HF_ENDPOINT=https://hf-mirror.com \
    /data/venvs/vllm-ds4/bin/hf download nvidia/MODEL --local-dir /data/models/<model> \
    --repo-type model --max-workers 2 \
    </dev/null >/dev/null 2>&1"

# 4. Verify it's alive (check immediately after starting)
ssh jianliu@10.10.70.96 "pgrep -fa 'hf download nvidia/MODEL' | grep -v grep"

# 5. Monitor: du -sh = cumulative bytes; safetensors in final dir = completed shards
ssh jianliu@10.10.70.96 "du -sh /data/models/<model>/ && \
  find /data/models/<model> -maxdepth 1 -name 'model-*.safetensors' | wc -l && \
  find /data/models/<model>/.cache -name '*.lock' | wc -l"

# 6. View log
ssh jianliu@10.10.70.96 "cat /tmp/hf_download_<model>.log | tr '\\r' '\\n' | tail -5"

# Kill stale download
ssh jianliu@10.10.70.96 "pkill -f 'hf download nvidia/' && \
  rm -rf /data/models/<model>/.cache/huggingface/"
```

**Key facts:**
- Huggingface.co direct is blocked from 70.96 (curl error 28/timeout). hf-mirror.com works via proxy.
- Always use `HF_ENDPOINT=https://hf-mirror.com`.
- `.lock` files in cache = active workers. When a shard finishes, it lands in `$LOCAL_DIR` as `model-XXXXX-of-XXXXX.safetensors`.
- **No `--resume-download` flag in `hf` CLI** — hf auto-resumes by checking etag. Use Python API `snapshot_download(resume_download=True)` for explicit control.
- **XetHub CAS signed URLs expire**: many `nvidia/` quantized models store files on XetHub CAS (`cas-bridge.xethub.hf.co`). The hf-mirror.com redirect embeds a signed URL valid ~1 hour. If CAS returns 403, the URL is stale — re-fetch the redirect to get a fresh signed URL.
- **Use `--max-workers 2`** — default 8 causes silent death on large files.
- Files: 49×~10GB safetensors + config/tokenizer. At ~20 MB/s, expect 6–8 hours.

## References

- **Two vLLM instances on 70.98** (2026-06-03): Both `vllm-ds4` (PID 621522) AND `vllm-latest-cu130` (PID 620441) were running simultaneously — each consuming ~80 GB/gpu vs ~75 GB/gpu on 70.96 (master). The extra ~5 GB/card (~40 GB total) is wasted GPU memory. Only one instance is needed. Always kill ALL vLLM instances before starting a new one:
  ```bash
  ssh jianliu@10.10.70.98 "pkill -9 -f 'vllm serve'; sleep 2; nvidia-smi --query-gpu=memory.used --format=csv,noheader"
  ```

- **GPU memory exhaustion from stale processes** — Multi-node clusters hard-killed via `kill -9` on the master leave orphan GPU worker processes (e.g. `VLLM::Worker_PP*`) holding 100% of VRAM on the worker node. A subsequent startup fails immediately with:
  ```
  ValueError: Free memory on device cuda:N (X.XX/YY.ZZ GiB) on startup is less than
  desired GPU memory utilization (0.XX, ZZ.ZZ GiB)
  ```

  **Diagnostic:** `nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | sort -t',' -k2 -rn`
  **Fix:** Explicitly `kill -9` all stale PIDs across ALL nodes before any restart.
  **Pre-startup check:**
  ```bash
  for node in 96 98; do
    ssh jianliu@10.10.70.$node "nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader"
    ssh jianliu@10.10.70.$node "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | sort -t',' -k2 -rn"
  done
  ```
- **Blackwell (sm120) + NCCL 2.28.9 incompatibility** — The torch-bundled NCCL 2.28.9 does not support Blackwell compute capability 12.0. Symptom: `NCCL error: invalid usage` during `ncclCommInitRank` or `NCCL error: unhandled system error` during `ncclAllReduce`. System NCCL 2.30.4 supports sm120 but swapping the .so into the venv may cause pynccl_wrapper API version mismatch. **Fix:** GPU reset (`sudo nvidia-smi -r` or reboot) sometimes resolves transient NCCL state corruption. If persistent, the NCCL library in the venv needs to be upgraded to ≥ 2.30.
- **Proxy required** — Always `source ~/.bashrc` before any command. Non-interactive SSH never loads `.bashrc`.
- **Gloo 127.0.1.1 bug** — `/etc/hosts` maps `127.0.1.1 → oem96`, causing Gloo TCPStore to fail when `mode=VLLM_COMPILE`. Workaround: set `MASTER_ADDR=192.168.66.10` and `VLLM_HOST_IP=192.168.66.10`.
- **5-minute EngineCore handshake timeout** — The ds4-sm120 vLLM branch has a hard-coded 300-second timeout in `startup_handshake`. With DeepSeek-V4-Pro (806 GB, FP8, 1M context), KVCache profiling + compile mode=3 can exceed this, even on a single-node DP=1 setup. Symptoms: `RuntimeError: Did not receive response from front-end process within 5 minutes` in the log after ~5 minutes of apparent inactivity. Workarounds: reduce `max-model-len`, lower `gpu-memory-utilization`, add `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1`, or avoid DP > 1.
- **Port reuse** — Master port can get stuck with TCP store from previous run. Always use a new port on restart.
- **`VLLM::Worker_TP*` orphan processes hold GPU memory invisibly** (gid 138). `jianliu` is only in groups `jianliu` and `sudo`. Either `sudo usermod -aG docker jianliu` (then re-login) or use `sudo -S` with password piped over SSH. Password for all sudo on this cluster: `!QAZ2wsx`.
- **`VLLM::Worker_TP*` orphan processes hold GPU memory invisibly** — When the vLLM API server process is killed (even with `kill -9`), worker subprocess `VLLM::Worker_TP*` can become orphans that remain invisible to `ps aux | grep vllm` but hold **57,834 MiB/gpu** as shown by `nvidia-smi --query-compute-apps`. Always check `nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv` to confirm GPU is actually free before restarting. Workers survive because they are direct children of init/PID 1 after the parent dies.
- **`!` in password** — When using the password in bash, wrap in single quotes: `'!QAZ2wsx'` to prevent history expansion.
- **ConnectX-6 vs Intel NIC** — `ens20f0` is the 1GbE Intel NIC, `ens35f0np0` is the 100G ConnectX-6. NCCL must use `ens35f0np0` for multi-node communication.
- **RDMA device name differs per node** — 70.96 RDMA device is `rocep200s0f0`, 70.98 is `mlx5_bond_0`. NCCL_IB_HCA must match the local node's RDMA device. If mismatched, NCCL fails with `Failed to initialize any NET plugin`. Always auto-detect with `rdma link show`.
- **FlashInfer irrelevant** — DeepSeek V4 uses MLA attention (Triton backend). FlashInfer autotune flags have no effect.

## Network Hardware Discovery

Quick check for NIC inventory on a node:

```bash
lspci | grep -i mellanox          # physical card
ip -br link show                   # all interfaces
ethtool ens35f0np0 | grep Speed    # link speed
rdma link show                     # RDMA state
ls /sys/class/infiniband/          # IB devices
lsmod | grep mlx5                  # driver loaded
```

## References

Detailed notes in `references/`:
- `references/70-96-detailed-setup.md` — Full setup details
- `references/70-96-models.md` — Models under /data/models/ with sizes and download status
- `references/glm5-fp8-debug-2026-06-03.md` — GLM-5.1-FP8 startup script venv bug + FlashInfer MLA fix (2026-06-03)
- `references/glm5-nvfp4-model-config.md` — GLM-5.1-NVFP4 model config, parallelism strategy, vLLM args
- `references/glm5-nvfp4-bench.md` — vLLM serve benchmark commands, test matrix, diagnostics for GLM-5.1-NVFP4
