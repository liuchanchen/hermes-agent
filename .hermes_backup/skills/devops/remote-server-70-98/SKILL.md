---
name: remote-server-70-98
description: Remote GPU server management for 10.10.70.98 (oem98) — NVIDIA RTX PRO 6000 Blackwell Server Edition (8×, 96GB each), Mellanox ConnectX-6 Dx NICs, NFS mount, initial setup and operations.
version: 1.0.1
author: Hermes Agent
license: MIT
---

# Remote Server 10.10.70.98 — NVIDIA RTX PRO 6000 Blackwell Server Edition

## Hardware Specs

| Component | Detail |
|-----------|--------|
| **Hostname** | oem98 |
| **IP** | 10.10.70.98 |
| **GPU** | 8× NVIDIA RTX PRO 6000 Blackwell Server Edition |
| **GPU Memory** | 97,887 MiB (~96 GB) each |
| **Compute Capability** | 12.0 |
| **Driver** | 595.58.03 (nvidia-driver-595-open) |
| **CUDA Driver** | 13.2 |
| **CUDA Toolkit** | 13.2 (cuda-nvcc-13-2) |
| **Python** | 3.12.13 with /data/venvs/vllm-ds4/ |

## Current Service (2-node DP=2 cluster with 70.96)

As of 2026-05-23, 70.98 runs as a **DP peer (node-rank=1, headless)** in a 2-node Data Parallel cluster:

| Node | Role | GPU | Memory |
|------|------|-----|--------|
| 70.96 (oem96) | master, node-rank=0, API server | RTX 5090 × 8 | 32 GB each |
| 70.98 (oem98) | peer, node-rank=1, headless (no HTTP) | RTX PRO 6000 × 8 | 96 GB each |

**Model:** deepseek_v4_pro (DeepSeek-V4-Pro, ~806 GB)
**Strategy:** TP=8 (intra-node) + DP=2 (inter-node, data parallelism) + EP enabled
**API key:** sk-warpdriveai
**Context length:** 1,048,576
**Async scheduling:** enabled (disables NCCL for DP sync between nodes)

### Architecture (Current: DP=2)

This is **DP=2 (data parallelism) with async scheduling** — **NOT** PP=2 (pipeline parallelism):

- Each node holds a **complete copy** of the model (weights sharded by TP+EP within each node)
- DP replicas process **different requests in parallel**
- Only node-rank=0 (70.96) starts the HTTP API server
- 70.98 runs EngineCore + GPU Workers only — **no HTTP endpoint**

**Startup script:** `/data/venvs/vllm-ds4/start_dsv4_pro_tp8_dp2_ep.sh` — auto-detects hostname to determine master vs worker role. Both nodes run the **same** command:

```bash
bash /data/venvs/vllm-ds4/start_dsv4_pro_tp8_dp2_ep.sh
```

**Network:** Uses ConnectX-6 Dx 100GbE RoCE v2 (`ens35f0np0`, 10.10.71.x network) with NCCL IB Verbs transport:

```bash
export NCCL_SOCKET_IFNAME=ens35f0np0
export GLOO_SOCKET_IFNAME=ens35f0np0
export TP_SOCKET_IFNAME=ens35f0np0
export VLLM_HOST_IP="10.10.71.98"
export MASTER_ADDR="10.10.71.96"
export NCCL_IB_DISABLE=0
export NCCL_IB_HCA=mlx5_0
export NCCL_NET=IB
```

**Log redirection** uses direct file redirect (NOT `tee`) to avoid the tee process death → SIGPIPE problem:

```bash
vllm serve ... > "$LOG_FILE" 2>&1
```

Log file: `/tmp/vllm_tp8_dp2_$$.log`
```bash
--pipeline-parallel-size 1
--data-parallel-size 2 --data-parallel-size-local 1
--data-parallel-backend mp
--nnodes 2 --node-rank 1
--master-addr 10.10.71.96 --master-port 29505
--data-parallel-address 10.10.71.98
--data-parallel-rpc-port 29550
--enable-expert-parallel
--kv-cache-dtype fp8 --block-size 256
--max-model-len 1048576 --gpu-memory-utilization 0.93
--max-num-seqs 512 --max-num-batched-tokens 8192
--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_AND_PIECEWISE"}'
--tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4
--enable-auto-tool-choice --reasoning-parser deepseek_v4
--served-model-name deepseek_v4_pro
```

### Important: Worker Node Does NOT Serve HTTP

`curl http://localhost:8000/health` on 70.98 will **fail** (connection refused). This is expected — only the master node (70.96) binds port 8000.

To verify the cluster is healthy:
1. Check 70.98's GPU workers: `ps aux | grep VLLM::Worker`
2. Check 70.96's API: `curl http://10.10.70.96:8000/health`
3. Send a real chat completion to 70.96 (try twice if first request times out — Triton JIT warmup):
   ```bash
   curl -s -X POST http://10.10.70.96:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek_v4_pro","messages":[{"role":"user","content":"hi"}],"max_tokens":100}'
   ```
4. Check master logs for "200 OK" responses

### Start command (current: DP=2, 100G RoCE)

Both nodes run the same script — it auto-detects master vs worker by hostname:

```bash
bash /data/venvs/vllm-ds4/start_dsv4_pro_tp8_dp2_ep.sh
```

The script handles all env vars (NCCL, Gloo, RoCE) internally. Logs go to `/tmp/vllm_tp8_dp2_$$.log` via direct file redirect (no `tee`).

### Pitfalls

- **Gloo bug on 70.96** — `/etc/hosts` maps `127.0.1.1 → oem96`, causing Gloo TCPStore to fail when `mode=VLLM_COMPILE`. Workaround: set `MASTER_ADDR=10.10.70.96` and `VLLM_HOST_IP=10.10.70.96`.
- **Gloo 127.0.1.1 bug on 70.98** — Ubuntu default `/etc/hosts` maps hostname to `127.0.1.1`. In multi-node DP setups, this causes Gloo to bind to loopback and fail cross-node connections: `Gloo connectFullMesh failed with ... Connection refused, remote=[127.0.1.1]:PORT`. Fix: `sudo sed -i "/oem98/d" /etc/hosts && echo "10.10.71.98  oem98" | sudo tee -a /etc/hosts`
- **CUDA context not freed on pkill** — Killing vLLM with `pkill -9` leaves ~90 GB GPU memory allocated. The CUDA contexts are held by orphaned GPU worker processes (e.g. `VLLM::Worker_PP*`, `VLLM::Worker_DP1_TP*`). On the next startup, vLLM fails with `ValueError: Free memory on device cuda:N (X/YY GiB) on startup is less than desired GPU memory utilization (0.88, ZZ GiB)`.

  **Diagnostic:**
  ```bash
  ssh jianliu@10.10.70.98 "nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader | sort -t',' -k2 -rn"
  ```

  **Fix:** Explicitly kill all stale PIDs:
  ```bash
  ssh jianliu@10.10.70.98 "kill -9 <pid1> <pid2> ... <pidN>"
  ```

  **Verify:**
  ```bash
  ssh jianliu@10.10.70.98 "nvidia-smi --query-gpu=free,memory.used --format=csv,noheader"
  ```

  Xorg/gdm3 also pins GPU memory. Check: `nvidia-smi -q | grep -i 'pid\|process' | grep -v 'N/A'`
- **Port reuse** — Master port can get stuck with TCP store from previous run. Always use a new port on restart.
- **Context length vs memory** — `--max-model-len 1048576` works on this TP=8+PP=2 setup with gpu_mem=0.90. Increasing to 0.95 may cause OOM.
| **CPU** | Intel Xeon Gold 6530 (128 threads) |
| **RAM** | 1.0 TiB |
| **Disk (root)** | 1.7 TB LVM (13 GB used, 1.6 TB free) — `/dev/mapper/vgubuntu-root` |
| **Disk (data)** | 3.5 TB LVM — `/dev/mapper/datavg-datalv` mounted at `/data` (2.0G used, 3.3T free — model storage) |
| **NFS** | `/nasdata` — NFS mount from `10.10.80.223:/volume1/sharedata/software` (131 TB, 71 TB used) |
| **NICs** | Mellanox ConnectX-6 Dx (MT2892 Family) — dual-port, `ens35f0np0` (100G, bond0 slave, RDMA IP: **192.168.66.20/24** via bond0), `ens35f1np1` (unused) |
| **RDMA device** | `mlx5_bond_0` (bonded RDMA — **different** from 70.96's `rocep200s0f0`) |
- **`ens20f0` is 100 Mb/s, NOT 1 GbE** — This NIC auto-negotiates at 100 Mb/s (same issue as 70.88). All network transfers via ens20f0 are bottlenecked to ~5-6 MB/s. For large data transfers (models, datasets), use the bond0/192.168.66.x network instead: `rsync -aP --partial source/ jianliu@192.168.66.20:/data/models/dest/`
| **System** | Ubuntu 22.04.1 LTS, Kernel 5.15.0-43-generic |
| **nvidia-persistenced** | v595.58.03 (running) |

## GPU Topology

- **NUMA 0** — GPU0-3, CPU 0-31,64-95 (connected via NODE)
- **NUMA 1** — GPU4-7, CPU 32-63,96-127 (connected via NODE)
- **Cross-NUMA** — SYS (PCIe + QPI/UPI)
| **NIC0** — RDMA device `mlx5_bond_0` (on NUMA1 side — PIX to GPU4-7, SYS to GPU0-3)
- **PCIe** — Gen5 ×16 under load (32 GT/s), Gen1 ×16 when idle (P8 power state downclock). nvidia-smi shows `Device Max=Gen5, Host Max=Gen5, Current=Gen1(idle)/Gen5(load)`
- **No NVLink** — RTX PRO 6000 Blackwell Server Edition has no NVLink; PCIe only
- **NCCL latency** (8B, all_reduce): ~35 us (8-card), ~9 us (2-card within NUMA)
- **NCCL BusBW peak**: ~39-40 GB/s (8-card, cross-NUMA via QPI/UPI)
- **2-card all_reduce (within NUMA)**: 34.12 GB/s AlgoBW, 8.6 us latency — full Gen5 ×16 saturation
- **NCCL collective ranking (8-card)**: all_gather (42.66 GB/s) > broadcast (40.13 GB/s) > all_reduce (39.30 GB/s BusBW) > reduce_scatter (26.87 GB/s) > sendrecv (24.95 GB/s) > alltoall (15.56 GB/s)

### Alltoall Benchmark (2026-06-22, vs 70.88)

Alltoall is N²-communication and far more sensitive to cross-NUMA penalty and CPU/NCCL differences than all_reduce.

| Server | CPU | NCCL | 4-GPU avg busbw | 8-GPU avg busbw | 8/4 ratio | 8-GPU peak busbw |
|--------|-----|------|----------------:|----------------:|:---------:|:----------------:|
| **70.88** | Xeon 8558P (48c, 260MB L3) | 2.28.9 | 9.60 GB/s | 5.71 GB/s | 0.59x | 25.25 GB/s |
| **70.98** | Xeon Gold 6530 (32c, 160MB L3) | 2.30.4 | 8.68 GB/s | 3.70 GB/s | 0.43x | 13.05 GB/s |

70.98's 8-GPU alltoall is 54% slower than 70.88's. The 4-GPU (within-NUMA) gap is only ~10%, but 8-GPU (cross-NUMA) diverges dramatically. Root cause: CPU (fewer cores, smaller L3 cache) and potentially NCCL 2.30.4 suboptimal tuning for RTX PRO 6000 (device 10de:2bb5, class 0302). See `references/nccl-benchmark-results.md` in the `remote-server-management` skill for full per-size data.

## SSH Access

```bash
ssh jianliu@10.10.70.98 "command"
```

**No proxy needed** — this server has direct internet access (no HTTP proxy configured).

### Initial User Setup

The server was initially accessed via the `qs` user (password: `!QAZ2wsx`). The `jianliu` user was created with:

- Passwordless sudo (`/etc/sudoers.d/jianliu`)
- SSH key-based authentication (same key as other servers)

## Known Issues (2026-06-03)

### Two vLLM Instances Zombie Problem (CRITICAL)

When both `vllm-ds4` AND `vllm-latest-cu130` venv's vLLM processes start simultaneously on 70.98,
GPU memory consumption jumps ~5.5 GB/card higher than normal (~84% vs ~76%). Both instances
compete for GPU resources but only one is part of the active cluster. Verify with:

```bash
ssh jianliu@10.10.70.98 "ps aux | grep python3 | grep vllm | grep -v grep"
# If you see two sets of PIDs from different venv paths, one is zombie
```

**Fix:** Kill the orphan instance by its venv path:
```bash
ssh jianliu@10.10.70.98 "ps aux | grep vllm-latest-cu130 | grep -v grep | awk '{print \$2}' | xargs -r kill -9"
# Verify: nvidia-smi memory drops back to ~76% per card
```

### PP=2 ProcessGroupNCCL Crash — TCPStore Broken Pipe

When the worker's TCPStore loses the connection to the master's `192.168.66.10:29505`, workers
crash with a cascade of `sendBytes failed: Broken pipe` errors followed by zombie NCCL
heartbeat threads holding GPU memory. The cluster becomes non-functional.

Key error signature:
```
TCPStore.cpp:106 sendBytes failed on SocketImpl
  remote=[::ffff:192.168.66.10]:29505): Broken pipe
ProcessGroupNCCL.cpp:1826 [PG Id 0 Rank N]
  Failed to check "should dump" flag on TCPStore
  (TCPStore server has shut down too early)
```

**Recovery sequence:**
```bash
# 1. Kill all vLLM on BOTH nodes (worker first):
ssh jianliu@10.10.70.98 "pkill -f vllm; sleep 3"
ssh jianliu@10.10.70.96 "pkill -f vllm; sleep 3"

# 2. Increment MASTER_PORT and restart — worker first, then master:
ssh jianliu@10.10.70.98 "bash /data/venvs/vllm-ds4/start_glm5_fp8_2node.sh worker"
# Wait ~30s for worker to fully initialize
ssh jianliu@10.10.70.96 "bash /data/venvs/vllm-ds4/start_glm5_fp8_2node.sh master"

# 3. Verify: curl http://10.10.70.96:8000/v1/models returns model name
```

## Current Service: 2-Node PP=2 Cluster with 70.96

### DeepSeek-V4-Pro Worker

As of 2026-05-28, 70.98 runs as a **PP=2 worker (node-rank=1, headless)** in a 2-node Pipeline Parallel cluster:

### GLM-5.1-FP8 Worker

Also runs the same `start_glm5_fp8_2node.sh` script with `--headless --node-rank 1`. The worker node runs the `worker` argument:

```bash
bash /data/venvs/vllm-ds4/start_glm5_fp8_2node.sh worker
```

Note: The worker has transformers 5.8.0 pre-installed (master was upgraded from 4.57.6). Both nodes must have matching vLLM source code patches. Always clear `__pycache__` on both nodes after patching. **As of 2026-06-17, 70.98's vLLM source matches 70.88's (same base commit `b709b75` + same `common.py` flash-attn-4 fallback patch). The SM12 compatibility patches that were previously on 70.98 have been removed.**

## Current Setup State (as of 2026-05-18)

| Component | Status | Version |
|-----------|--------|---------|
| CUDA Driver | ✅ Installed | 13.2 (driver 595.58.03) |
| CUDA Toolkit (nvcc) | ✅ Installed | 13.2.78 |
| Python 3.12 | ✅ Installed | 3.12.13 (deadsnakes PPA) |
| NCCL (system) | ✅ Installed | 2.30.4-1+cuda13.2 |
| Docker | ❌ Not installed | — |
| NVIDIA Container Toolkit | ❌ Not installed | — |
| nccl-tests | ❌ Not compiled | — |

### Python venv: `/data/venvs/vllm-ds4/`

Created matching 70.88's environment. Key packages:

| Package | Version |
|---------|---------|
| Python | 3.12.13 |
| pip | 26.1.1 |
| torch | 2.11.0+cu130 |
| transformers | 5.8.0 |
| huggingface_hub | 1.13.0 |
| flashinfer | 0.6.8.post1 |
| xgrammar | 0.2.0 |
| vllm (fork) | ✅ Installed | 0.1.dev1+gb709b75b4 (jasl/vllm ds4-sm120, editable install) |
| CUDA Dev Libraries | ✅ Installed | cuda-libraries-dev-13-2 (cublas, cusparse, nvrtc, etc.) |
| cmake | ✅ Installed | 4.3.2 (pip, set as system default via update-alternatives) |
| ninja | ✅ Installed | 1.10.1 (apt) |
| NCCL (system) | ✅ Installed | 2.30.4-1+cuda13.2 |
| Docker | ❌ Not installed | — |
| NVIDIA Container Toolkit | ❌ Not installed | — |
| nccl-tests | ❌ Not compiled | — |

## DeepSeek-V4-Pro Deployment

### Single-node (not possible — OOM)
DeepSeek-V4-Pro weights total 806 GiB, cannot fit on 8×96 GB GPUs (768 GB total). Must use PP=2 with a second node.

### Current 2-Node PP=2 Cluster (as of 2026-05-28)

**Master (70.96):** node-rank=0, TP=8, PP=2, EP=8, HTTP API on port 8000
**Worker (70.98):** node-rank=1, TP=8, PP=2, EP=8, headless (no HTTP)

**Startup script:** `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh`

```bash
# Worker (70.98):
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh worker
# Master (70.96, after worker starts):
bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh master
```

**Network configuration (corrected for actual RDMA IPs):**
```bash
export NCCL_SOCKET_IFNAME=bond0          # was ens35f0np0 — FIXED: needs IP
export GLOO_SOCKET_IFNAME=bond0          # same fix
export TP_SOCKET_IFNAME=bond0
export VLLM_HOST_IP="192.168.66.20"      # was 10.10.71.98 — doesn't exist
export MASTER_ADDR="192.168.66.10"       # was 10.10.71.96 — doesn't exist
export NCCL_IB_HCA=mlx5_bond_0           # auto-detected: different from 70.96 (rocep200s0f0)
```

**Key differences from 70.96 startup config:**
- RDMA device is `mlx5_bond_0` (not `rocep200s0f0` like 70.96)
- VLLM_HOST_IP is `192.168.66.20` (not `.10`)
- The `start_dsv4_pro_2node.sh` script is **identical on both nodes** — it auto-detects master vs worker by the `$1` argument. The RDMA device is set per-node using `rdma link show` auto-detection.

### Startup Pitfalls (70.98 specific)

- **RDMA device name mismatch:** 70.98's RDMA device is `mlx5_bond_0`, **not** `rocep200s0f0` like 70.96. If `NCCL_IB_HCA` is set to `rocep200s0f0` on 70.98, NCCL fails with `Failed to initialize any NET plugin`. Always auto-detect with `rdma link show`.
- **GLOO needs an interface with an IP:** `ens35f0np0` has no IP (it's a bond slave). GLOO crashes with `Unable to find address for: ens35f0np0`. Must use `bond0` which has `192.168.66.20`.
- **Port reuse / ephemeral port exhaustion:** Leftover VLLM::Worker processes from failed runs hold stale TCPStore + ZMQ ephemeral ports. ZMQ randomly selects ephemeral ports on the RDMA IP (e.g., `tcp://192.168.66.20:45713`), and TIME_WAIT prevents immediate reuse after a crash. Fix: increment `MASTER_PORT` (e.g., 29507), or wait 60s for TIME_WAIT to clear. Check with `ss -tlnp | grep 192.168.66.20` and kill all stale PIDs.
- **Start order:** Worker first, then master. The worker waits for the master's TCPStore. Starting both simultaneously may cause "Connection closed by peer" errors if the worker connects before the master has finished init.

### API
**Endpoint:** `http://10.10.70.96:8000` (master only — worker has NO HTTP API)
**Model name:** `deepseek_v4_pro`

### Known Pitfalls
- **Port 29500 EADDRINUSE** — stale worker processes from failed starts can hold the port. Use `MASTER_PORT=29501` or fuser/kill stale processes.
- **Gloo 127.0.1.1 issue** — /etc/hosts on 70.96 maps `oem96` to `127.0.1.1`, causing Gloo TCPStore failures. Only affects local (intra-node) TP workers. Use different master_port to work around.
- **--compilation-config array expansion** — when using bash arrays `${SHARED_ARGS[@]}`, the JSON single quotes can be lost. Use inline command instead of array for `--compilation-config`.
- **vLLM compilation mode** — without explicit `--compilation-config`, default `mode: VLLM_COMPILE` (mode=3) will trigger inductor compilation which is slow and may cause Gloo timeouts.
| NCCL (torch bundled) | 2.28.9 |

### 1. Install CUDA Toolkit (nvcc)

No CUDA toolkit installed currently. Driver version 595.58.03 supports CUDA 13.2.

```bash
ssh jianliu@10.10.70.98 "echo 'PASSWORD' | sudo -S bash -c '
  wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
  dpkg -i cuda-keyring_1.1-1_all.deb
  apt-get update
'"

# Install nvcc matching driver CUDA version
ssh jianliu@10.10.70.98 "sudo -n apt-get install -y cuda-nvcc-13-2"
```

### 2. Install Docker

```bash
ssh jianliu@10.10.70.98 "sudo -N bash -c '
  apt-get update && apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \$(. /etc/os-release && echo \"\$VERSION_CODENAME\") stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io
  usermod -aG docker jianliu
'"
```

### 3. Install NVIDIA Container Toolkit

```bash
ssh jianliu@10.10.70.98 "sudo -N bash -c '
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed \"s#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g\" | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update && apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
'"
```

### 4. Install NCCL

```bash
ssh jianliu@10.10.70.98 "sudo -N apt-get install -y libnccl2 libnccl-dev"
```

### 5. Compile nccl-tests

```bash
ssh jianliu@10.10.70.98 "mkdir -p ~/work/bandwidth_test/ && cd ~/work/bandwidth_test/ && git clone https://github.com/NVIDIA/nccl-tests.git && cd nccl-tests && make -j\$(nproc)"
```

## NFS Mount Details

| Mount Point | Source | Size | Used |
|-------------|--------|------|------|
| `/nasdata` | `10.10.80.223:/volume1/sharedata/software` | 131 TB | 61 TB (47%) |
| `/data` | LVM (`datavg-datalv`) | 3.5 TB | 28K |

Contents of `/nasdata`: `sw2` directory (shared software repository).

## Inter-Server Model Transfer

To copy models between 10.10.70.98 and other servers in the subnet:

```bash
# 1. First add the source server's SSH public key to 98's authorized_keys:
# Get source's key:
ssh jianliu@10.10.70.88 "cat ~/.ssh/id_rsa.pub"
# Add it to 98:
ssh jianliu@10.10.70.98 'echo "<key-content>" >> ~/.ssh/authorized_keys'

# 2. Create destination directory (needs sudo for /data/):
ssh jianliu@10.10.70.98 "sudo -n mkdir -p /data/models && sudo -n chown jianliu:jianliu /data/models"

# 3. Run rsync from the source server (push mode):
ssh jianliu@10.10.70.88 "rsync -aP --partial /data/models/<model-name>/ jianliu@10.10.70.98:/data/models/<model-name>/"

# 4. To run in background with notification:
# Use terminal(background=true, notify_on_complete=true) from Hermes, 
# or nohup on the source:
ssh jianliu@10.10.70.88 "nohup rsync -aP --partial /data/models/<model-name>/ jianliu@10.10.70.98:/data/models/<model-name>/ > /tmp/rsync.log 2>&1 &"
```

**Note:** Neither server has the other's SSH key by default — you must add the key first.

### Current Models on /data/

| Model | Source | Size | Status |
|-------|--------|------|--------|
| deepseekv4_pro | 10.10.70.88 | ~806 GiB | Transferred 2026-05-18 |
| deepseekv4_flash | 10.10.70.88 | ~149 GiB | **Complete** (46/46 shards, 149 GB). `/data/models/deepseekv4_flash/`. rsync from 70.88 completed 2026-06-17. |
| Qwen3.6-35B-A3B-NVFP4 | 10.10.70.88 | 22 GB | Copied 2026-06-18. `/data/models/Qwen3.6-35B-A3B-NVFP4/`. |
| glm_5_1_fp8 | 10.10.70.96 | — | Available |

**DeepSeek-V4-Flash start script on 70.98:** `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`. Updated 2026-06-17 with adaptive TP support:
- `CUDA_VISIBLE_DEVICES` added (commented presets for 2/4/6/8 GPUs; defaults to all 8 if unset)
- `TP_SIZE` auto-detected: `TP_SIZE=$(echo "$CUDA_VISIBLE_DEVICES" | tr ',' '\n' | wc -l)`
- `MAX_LEN` fixed from `1,6384` (invalid commas) to `1048576`
- `MODEL_PATH` points to `/data/models/deepseekv4_flash`
- Usage: `CUDA_VISIBLE_DEVICES=0,1,2,3 bash start_dsv4_flash_1node.sh` (TP auto-set to 4)

Key vLLM flags: EP, `--reasoning-parser deepseek_v4`, `--tokenizer-mode deepseek_v4`, `--tool-call-parser deepseek_v4`, `--kv-cache-dtype fp8`, `--block-size 256`, `--enable-expert-parallel`, `--enable-ep-weight-filter`, `--compilation-config '{\"cudagraph_mode\":\"FULL_AND_PIECEWISE\", \"custom_ops\":[\"all\"]}'`.

For partial-GPU deployment: `CUDA_VISIBLE_DEVICES` + auto TP handles it. Reduce `--max-model-len` proportionally (~262144 for TP=4, ~131072 for TP=2). No other flags need changing — EP auto-scales with TP on single-node.

**70.98 now runs DeepSeek-V4-Flash single-node (as of 2026-06-17):** Started via `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`. Endpoint: `http://10.10.70.98:8000`. TP=8, all 8 GPUs loaded (~89 GB/97 GB each). Health check: `curl http://10.10.70.98:8000/health` → 200. Note: `curl` is not installed on 70.98 — use `python3 -c "import requests; ..."` or install curl.

**Benchmark results — DeepSeek-V4-Flash, TP=8, 1-node (70.98):**
Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf, EP enabled, kv-cache-dtype=fp8, block-size=256, max-model-len=1048576

Remote (70.88 → 70.98:8000) — 2026-06-17:

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0%        | 350.1       | 1784.2      | 10,870         | 150.3          |
| 40%       | 340.7       | 1736.5      | 12,043         | 152.7          |
| 80%       | 401.5       | 2046.0      | 8,413          | 131.5          |

Remote (70.88 → 70.98:8000) — 2026-06-18 (rerun):

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0%        | 304.9       | 1554.0      | 11,669         | 175.8          |
| 40%       | 361.6       | 1842.6      | 9,410          | 147.4          |
| 80%       | 403.2       | 2054.6      | 9,736          | 128.4          |

Local (70.98 → 70.98:8000) — 2026-06-18:

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0%        | 316.1       | 1610.7      | 11,716         | 168.3          |
| 40%       | 358.8       | 1828.3      | 9,539          | 148.5          |
| 80%       | 386.4       | 1968.9      | 9,125          | 133.4          |

**Benchmark results — DeepSeek-V4-Flash, TP=4 (4 GPUs), 1-node (70.98):**
Same config except `CUDA_VISIBLE_DEVICES=0,1,2,3` → TP auto-detected to 4.

Remote (70.88 → 70.98:8000) — 2026-06-18:

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0%        | 266.4       | 1357.5      | 16,780         | 195.7          |
| 40%       | 312.5       | 1592.2      | 13,294         | 167.0          |
| 80%       | 370.6       | 1888.5      | 11,186         | 139.0          |

TP=4 vs TP=8 comparison: ~15-25% lower throughput, ~55-60% higher TTFT at 0% cache, as expected with half the GPU resources.

**TP=4 rerun (20260618_113728, remote from 70.88):**

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0% | 270.8 | 1380.2 | 15,962 | 193.4 |
| 40% | 314.5 | 1602.8 | 13,210 | 165.8 |
| 80% | 381.9 | 1946.1 | 9,614 | 136.9 |

Results directories:
- TP=8 remote: `70.88:.../vllm_bench_results/20260617_224213/` and `20260618_095259/`
- TP=8 local: `70.98:.../vllm_bench_results/20260618_101854/`
- TP=4 remote: `70.88:.../vllm_bench_results/20260618_105249/` and `20260618_113728/`

### Qwen3.6-35B-A3B-FP8

**Available on 70.98** at `/data/models/Qwen3.6-35B-A3B-FP8/` (~35GB, rsync'd from 70.88 on 2026-06-18). Also on 70.88 at `/data/models/Qwen3.6-35B-A3B-FP8/`.

Start script: `~/work/tgu01-pro-model-deployment/qwen_3_6/start_qwen36.sh` (default DP=8 with all 8 GPUs).

**Single-GPU startup:**
```bash
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3.6-35B-A3B-FP8 \
  --host 0.0.0.0 --port 8000 --trust-remote-code \
  --gpu-memory-utilization 0.95 \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' \
  > /tmp/vllm_qwen36.log 2>&1 &
```

No `--reasoning-parser` or `--tokenizer-mode` flags needed for Qwen3.6 (unlike DeepSeek-V4/GLM).

**70.98 benchmark results — Qwen3.6-35B-A3B-FP8, 1 GPU:**
Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|-----------|-------------|-------------|----------------|----------------|
| 0% | 1800.7 | 9544.4 | 1,438 | 30.0 |
| 40% | 1824.5 | 9584.1 | 1,207 | 29.9 |
| 80% | 1801.4 | 9464.7 | 1,315 | 30.1 |

Results directory: `70.88:.../vllm_bench_results/20260618_171729/`

**Benchmark command patterns:**

Remote (from 70.88 targeting 70.98):
```bash
ssh jianliu@10.10.70.88 "source /data/venvs/vllm-ds4/bin/activate && \
  BASE_URL=http://10.10.70.98:8000 \
  SERVED_MODEL_NAME=/data/models/deepseekv4_flash \
  bash /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh"
```

Local (from 70.98 targeting itself):
```bash
ssh jianliu@10.10.70.98 "source /data/venvs/vllm-ds4/bin/activate && \
  MODEL=/data/models/deepseekv4_flash \
  BASE_URL=http://127.0.0.1:8000 \
  bash /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh"
```

**Important:** When running from 70.88, `SERVED_MODEL_NAME` must match the server's model path (`/data/models/deepseekv4_flash`), while `MODEL` uses the local tokenizer path (`/home/jianliu/work/models/deepseekv4_flash`). When running locally on 70.98, set `MODEL=/data/models/deepseekv4_flash` since the model exists at that path on 70.98.

Key vLLM flags: EP, `--reasoning-parser deepseek_v4`, `--tokenizer-mode deepseek_v4`, `--tool-call-parser deepseek_v4`, `--kv-cache-dtype fp8`, `--block-size 256`, `--enable-expert-parallel`, `--enable-ep-weight-filter`, `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", "custom_ops":["all"]}'`.

For partial-GPU deployment: `CUDA_VISIBLE_DEVICES` + auto TP handles it. Reduce `--max-model-len` proportionally (~262144 for TP=4, ~131072 for TP=2). No other flags need changing — EP auto-scales with TP on single-node.

**Docker installation (2026-06-21):** Docker 29.4.0 installed via deb packages from 70.88's aliyun mirror (download.docker.com unreachable from 70.98). Debs transferred to /tmp/docker_debs/ on 70.98, then `sudo dpkg -i`. `vllm/vllm-openai:nightly` image (20.3GB compressed, 41.1GB on disk) transferred from 70.88 via `docker save` → rsync → `docker load`. User `jianliu` added to docker group but `sudo` may still be needed for docker commands. `/data/venvs/vllm-ds4/` — editable install pointing to source tree at `/data/vllm-ds4-sm120/`. Base commit: `b709b75` (ds4-sm120 branch). Since it's an editable install (`pip install -e .`), Python source changes to `/data/vllm-ds4-sm120/vllm/` take effect immediately without rebuilding. Only C extension changes require a rebuild.

**vLLM source sync between 70.88 and 70.98:** Both servers have the same source tree at `/data/vllm-ds4-sm120/` installed in editable mode (commit `b709b75`, ds4-sm120 branch, with a single `common.py` flash-attn-4 try/except patch). The SM12 patches that were previously on 70.98 have been removed. To sync Python code: `scp` the changed `.py` files — no rebuild needed. For full rebuilds on 70.98, use `CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11' CC=gcc-11 CXX=g++-11 pip install -e . --no-build-isolation` and pre-rsync `.deps/` from 70.88 to skip slow CMake FetchContent git clones (30+ min on 70.98's 100 Mb/s NIC).

**70.98 SM12 patches removed (2026-06-17):** 70.98 previously carried 11 SM12/Blackwell compatibility patches on top of the base `b709b75` commit (adding `capability.major in [10, 12]` to MLA backends, sparse MLA fallback, `is_v32=False`, `num_stages=1` in triton decode attention). These were reverted to match 70.88's source tree. Consequence: vLLM on 70.98 will NOT select MLA attention backends for SM 12.0 GPUs — FlashInfer/FlashAttn backends will be used instead. DeepSeek-V4-Flash runs successfully without these patches (tested 2026-06-17, see benchmark results above). If MLA is needed on SM 12.0 (e.g., for GLM-5.1), these patches must be re-applied.

**Build pitfall — cc1plus not found on 70.98 (FIXED 2026-06-17):** The default `gcc` symlinked to `gcc-12` but `cc1plus` only existed for gcc-11. Applied `sudo ln -sf gcc-11 /usr/bin/gcc` so both build-time and runtime JIT (Triton/tilelang) compilation work. Verify: `gcc --version | head -1` → should show `gcc-11`. Build still needs `CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11' CC=gcc-11 CXX=g++-11 pip install -e . --no-build-isolation` for cmake to find the right host compiler.

**Build pitfall — slow CMake FetchContent on 70.98:** CMake FetchContent clones CUTLASS, Triton kernels, flash-attn etc. from GitHub. On 70.98's 100 Mb/s `ens20f0`, git clone of Triton alone takes 30+ minutes. **Fix:** rsync `.deps/` from a server that already built successfully (e.g., 70.88): `rsync -avz --progress jianliu@10.10.70.88:/data/vllm-ds4-sm120/.deps/ /data/vllm-ds4-sm120/.deps/` (~30s for 2.6GB over 10GbE). Then `rm -rf build` (NOT `.deps/`) before rebuilding.

**70.88 NIC bottleneck for model transfers:** 70.88's `ens20f0` negotiates at 100 Mb/s, capping rsync throughput to ~5 MB/s. A 149G transfer takes ~8 hours. If faster transfers are needed, consider using an intermediate node with 1 GbE+ management NIC or bringing up 70.88's `ens35f0np0`/`ens35f1np1` (100GbE, currently DOWN).

## Key Differences from Other 10.10.70.x Servers

- **No HTTP proxy** — direct internet access (unlike 70.88, 95, 96)
- **RTX PRO 6000 Blackwell Server Edition** (96 GB) — not RTX 5090 (32 GB) like 88/93/95/96
- **Larger GPU memory** (96 GB vs 32 GB) — suitable for larger models
- **PCIe Gen 4 x16** — all GPUs (currently shows Gen 1, may just need GPU workload to ramp)
- **Dual ConnectX-6 Dx** NICs — for potential RDMA/network connectivity
- **Fresh installation** — minimal software installed, no CUDA toolkit, no Docker, no NCCL

## References

Detailed server-specific notes in `references/`:
- `references/70-98-detailed-setup.md` — Full setup details

## Pitfalls

- **No proxy** — unlike 88/95/96, no need for `source ~/.bashrc` for proxy
- **SSH key pair may be missing** — 70.98 may not have a local SSH key pair (`~/.ssh/id_ed25519` or `~/.ssh/id_rsa`) — it only had `authorized_keys` and `known_hosts` initially. This means other nodes cannot SSH into 70.98 (no public key to authorize). For multi-node operations requiring bi-directional SSH, generate with `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ''` and add the pubkey to `~/.ssh/authorized_keys` on the peer nodes. **Note: key was generated during the 2026-05-30 session — verify current state before assuming it exists.**
- **No CUDA toolkit** — nvcc not available, must be installed
- **No Docker** — must install from scratch
- **No NCCL** — must install separately
- **GPU currently at PCIe Gen 1** — bandwidth may be limited; idle GPUs downclock PCIe; running a CUDA workload should bring it to Gen 4
- **`qs` user access** — initial access via `qs` account is still available, but `jianliu` is the primary operational user
- **Do not hardcode passwords** — prefer SSH key auth for automated tasks
- **SSH key setup required for inter-server transfers** — neither this server nor its peers have each other's keys by default. Must manually add the source server's public key to authorize_keys before rsync. When appending via piped commands, single-quote expansion can fail silently — use `echo "$KEY" >> ~/.ssh/authorized_keys` from a properly expanded context, or inline the full key in quotes.
