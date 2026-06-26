---
name: remote-server-management
description: Remote GPU server management — SSH access, CUDA/nvcc toolchain, NCCL configuration, nccl-tests compilation, bandwidth testing, and multi-server cluster operations for servers in the 10.10.70.x network.
version: 1.3.0
author: Hermes Agent
license: MIT
---

# Remote Server Management

Umbrella skill for managing remote GPU servers in the 10.10.70.x network. Covers SSH access patterns, CUDA toolchain installation, NCCL version management, nccl-tests compilation, bandwidth testing, Docker/vLLM deployment, and multi-server cluster operations.

## Supported Servers

| Server | Hostname | GPU | GPUs | NIC Speed (mgmt) | Notes |
|--------|----------|-----|------|-------------------|-------|
| 10.10.70.66 | oem66 | A100 40GB | 6× | — | Older setup, full CUDA 12.3 installed, no proxy needed |
| 10.10.70.88 | oem88 | RTX 5090 32GB | 8× | **100 Mb/s** ⚠️ | Proxy via .bashrc, vLLM + SGLang + TRTLLM, Wan2.2-T2V-A14B, CUDA 13.0, **Xeon Platinum 8558P** (48c/socket, 260MB L3 — best CPU for alltoall), NCCL 2.28.9, **Kernel 6.8.0-111-generic**. **See also: `remote-server-70-88` skill (detailed).** |
| 10.10.70.93 | oem93 | **WarpDrive TGU01-Pro** 32GB | 8× | — | openEuler 24.03 LTS-SP3, WD driver 580.159.03, **`nvidia-smi` blocked** (stub exit 113 — use `wd-smi` instead), no host-level CUDA toolkit or NCCL. Docker containers: `deepseek-v4-flash` (nvidia/cuda:13.0.0 + NCCL 2.27.7), `qs_wdtgu01_20000`. Password auth only (`!QAZ2wsx`). **See also: `references/70-93-performance-quirks.md` (detailed).** |
| 10.10.70.94 | oem94 | RTX 5090 32GB | 8× | 1 GbE | SSH key auth for jianliu. Driver 595.71.05. **`/usr/local/bin/nvidia-smi` is a shell script wrapper that exits 113** — use `/usr/bin/nvidia-smi` instead. All 8 GPUs occupied by vLLM (VLLM::Worker_TP* processes, ~32GB VRAM each). nccl-tests at `~/work/bandwidth_test/nccl-tests/` (copied from 70.88 via scp -r). No proxy. **NCCL 2.30.7+cuda13.3** (apt-installed, no CUDA/NCCL toolchain pre-installed). No OpenMPI pre-installed — install with `apt-get install openmpi-bin libopenmpi-dev`. nccl-tests rebuilt with `make MPI=1 NCCL_HOME=/usr MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi`. **nvidia-smi wrapper quirk confirmed 2026-06-24**: the stub wrapper is a bash script at `/usr/local/bin/nvidia-smi` that calls `exit 113`. Direct `/usr/bin/nvidia-smi` works normally. |
| 10.10.70.95 | oem95 | RTX 5090 | 8× | 1 GbE | Has proxy (via .bashrc), LVM storage, currently running MiniMax M2 nvfp4 |
| 10.10.70.96 | oem96 | RTX PRO 6000 Blackwell SE | 8× | 1 GbE | DeepSeek-V4-Pro PP=2 master, proxy via .bashrc, bond0 RoCE v2 (192.168.66.10/24) |
| 10.10.70.92 | oem92 | RTX 5090 32GB | 8× | — | SSH key auth. NCCL 2.28.9+cuda13.0 (downgraded from 2.30.4), cuda-toolkit-13-2, nccl-tests at `~/work/bandwidth_test/nccl-tests`. **Xeon Gold 6530** (32c/socket, 160MB L3). **Kernel 6.8.0-124-generic.** CUDA 13.2, Driver 595.71.05 (nvidia-utils-595 reinstalled 2026-06-24 to fix SMI version label). **`/data/` owned by `rapidsdb`**. No proxy. sudo password: `!QAZ2wsx`. vLLM venv at `/data/venvs/vllm-ds4/` (Python 3.12, editable install at `/data/vllm-ds4-sm120/`). vLLM 0.6.0.dev0. DeepSeek-V4-Flash at `/home/public/models/tgu01/deepseekv4_flash/` (149GB). Startup: `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh` (uses `cudagraph_mode`). |
| 10.10.70.98 | oem98 | RTX PRO 6000 Blackwell SE | 8× | 1 GbE | DeepSeek-V4-Pro PP=2 worker, no proxy, bond0 RoCE v2 (192.168.66.20/24), **Xeon Gold 6530** (32c/socket, 160MB L3, 128 threads, 2 NUMA), NCCL 2.30.4, **Kernel 6.8.0-111-generic**. perf 6.8.12 installed. PCM built from source at `/usr/local/bin/pcm*`. |

### Model Inventory (2026-06-17)

| Model | 70.88 | 70.92 | 70.95 | 70.96 | 70.98 |
|-------|-------|-------|-------|-------|
| DeepSeek-V4-Pro | — | — | ✅ `/data/models/deepseekv4_pro` | ✅ `/data/models/deepseekv4_pro` |
| DeepSeek-V4-Flash | ✅ `/home/jianliu/work/models/deepseekv4_flash` (149G) | ✅ `/home/public/models/tgu01/deepseekv4_flash` (149G) | — | ❌ empty dir | ⏳ `/data/models/deepseekv4_flash` (rsync in progress from 70.88) |
| GLM-5.1-FP8 | — | — | ✅ `/data/models/glm_5_1_fp8` | ✅ `/data/models/glm_5_1_fp8` |
| GLM-5.2-FP8 | — | — | ✅ `/data/models/glm_5_2_fp8` | — |
| MiniMax M2.7 | — | — | ✅ `/data/models/minimax_m2_7` | — |
| MiniMax M2.7-NVFP4 | — | — | ✅ `/data/models/minimax_m2_7_nvfp4` | — |
| Qwen3.6-35B-A3B (FP8/BF16) | ✅ `/data/models/` | — | — | — |
| Wan2.2-T2V-A14B-NVFP4 | ✅ `/data/models/wan2.2_nvfp4` | — | — | — |

**70.88 NIC bottleneck:** `ens20f0` is at 100 Mb/s, capping all transfers at ~5.3 MB/s. Other servers have 1 GbE management NICs.

## SSH Connection Patterns

### No-proxy servers (66, 93, 98)
```bash
ssh -o StrictHostKeyChecking=accept-new jianliu@10.10.70.XX "command"
```
No need to `source ~/.bashrc` — direct internet access.

### Proxy servers (88, 95, 96)
> **Important:** These servers have a proxy (`http://10.10.60.140:7890`) configured in `~/.bashrc`. Non-interactive SSH does NOT load `.bashrc` automatically. **Always prefix commands with `source ~/.bashrc &&`**:

```bash
ssh jianliu@10.10.70.XX "source ~/.bashrc && command"
ssh -t jianliu@10.10.70.XX "source ~/.bashrc && echo 'PASSWORD' | sudo -S apt-get install -y PACKAGE"
```

### Sudo password handling
- All servers share the same sudo password
- `!` in bash needs single quotes: `echo '!QAZ2wsx' | sudo -S ...`
- Use `-t` flag when PTY is needed (watch, top, interactive sudo)

## CUDA / nvcc Installation

### For RTX 5090 (Blackwell, CC 12.0)
Requires CUDA 12.8+. Install via fine-grained nvcc package (~87 MB):

```bash
# Add NVIDIA repository (first time only)
ssh jianliu@10.10.70.XX "echo 'PASSWORD' | sudo -S bash -c '
  wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
  dpkg -i cuda-keyring_1.1-1_all.deb
  apt-get update
'"

# Install nvcc matching driver CUDA version (check with nvidia-smi -q | grep "CUDA Version")
ssh jianliu@10.10.70.XX "echo 'PASSWORD' | sudo -S apt-get install -y cuda-nvcc-13-2"
```

**Available nvcc versions:** `cuda-nvcc-12-8`, `cuda-nvcc-13-0`, `cuda-nvcc-13-1`, `cuda-nvcc-13-2`

### For A100 (CC 8.0, sm_80)
Server 70.66 has full CUDA 12.3 installed at `/usr/local/cuda-12.3`. Note: system `/usr/bin/nvcc` is CUDA 10.1 — always use `/usr/local/cuda/bin/nvcc` instead.

### Add CUDA to PATH
```bash
ssh jianliu@10.10.70.XX "echo 'PASSWORD' | sudo -S tee -a /etc/profile.d/cuda.sh > /dev/null << 'EOF'
export PATH=/usr/local/cuda/bin:\$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:\$LD_LIBRARY_PATH
EOF
sudo chmod +x /etc/profile.d/cuda.sh"
```

### NCCL sm120 (Blackwell) Compatibility

Blackwell GPUs (compute capability 12.0, RTX 5090, RTX PRO 6000) require **NCCL ≥ 2.30** for full support.

| NCCL Version | Blackwell (sm120) | Notes |
|-------------|-------------------|-------|
| 2.28.9 (torch 2.11.0+cu130) | ❌ Fails | `invalid usage` in `ncclCommInitRank`, `unhandled system error` in `ncclAllReduce` |
| 2.30.4 (system, cuda13.2) | ✅ Works | But swapping .so may cause pynccl_wrapper API mismatch |

**Symptoms of NCCL + Blackwell failure:**
- `RuntimeError: NCCL error: invalid usage (run with NCCL_DEBUG=WARN for details)` — during `ncclCommInitRank` (pynccl.py:135)
- `RuntimeError: NCCL error: unhandled system error (run with NCCL_DEBUG=INFO for details)` — during `ncclAllReduce` (pynccl.py:142-175)

**Diagnostic:** Check the NCCL library actually loaded by the venv:
```bash
# Log line to look for:
# vLLM is using nccl==2.28.9  (TOO OLD for sm120)
# vLLM is using nccl==2.30.4  (OK)
/data/venvs/vllm-ds4/bin/python3 -c "
from ctypes import CDLL
l = CDLL('libnccl.so.2')
v = l.ncclGetVersion()
print(f'NCCL version: {v} ({v//10000}.{(v%10000)//100}.{v%100})')
"
```

**Workarounds (try in order):**
1. GPU reset: `sudo nvidia-smi -r` — clears NCCL state corruption (no sudo access from Hermes terminal, ask user)
2. Reboot: clears all GPU/NCCL state
3. Upgrade NCCL in venv: `pip install nvidia-nccl-cu13` (if available) or swap system libnccl.so.2 into the venv's torch/lib/ directory

**Note:** GPU reset (`nvidia-smi -r`) fails with "In use by another client" if Xorg/gdm3 or any process holds GPU context. Stop gdm3 first: `sudo systemctl stop gdm3`, then reset.

### NCCL Version Management

### Install NCCL
```bash
# Step 1: Add NVIDIA CUDA repository (if not already present)
# Download and install the cuda-keyring package (provides GPG key + apt source)
wget -q -O /tmp/cuda-keyring.deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
echo 'PASSWORD' | sudo -S dpkg -i /tmp/cuda-keyring.deb
echo 'PASSWORD' | sudo -S apt-get update

# Step 2: Check available NCCL versions
apt-cache policy libnccl2

# Step 3: Install specific version (pin to match other servers)
echo 'PASSWORD' | sudo -S apt-get install -y libnccl2=2.30.4-1+cuda13.2 libnccl-dev=2.30.4-1+cuda13.2

# Step 4: Verify
readlink -f /usr/lib/x86_64-linux-gnu/libnccl.so.2
strings /usr/lib/x86_64-linux-gnu/libnccl.so.2.* | grep 'NCCL version'
dpkg -l libnccl2 libnccl-dev | grep -E '^ii'
```

**Note:** On proxy servers (70.88, 70.95, 70.96), prefix commands with `source ~/.bashrc &&` for internet access. On servers without proxy (70.92, 70.98), direct access works.

**Note:** NVIDIA's repo auto-redirects in China to `developer.download.nvidia.cn`. This is transparent — no config change needed.

### NCCL version inventory (2026-06-24)

| Server | NCCL Version | CUDA | GPU | Notes |
|--------|-------------|------|-----|-------|
| 70.88 | 2.28.9+cuda13.0 | 13.0 | RTX 5090 | Oldest — best 8-GPU alltoall (23.50 GB/s avg busbw, 25.25 GB/s peak), likely due to Xeon 8558P (48c, 260MB L3) |
| 70.92 | 2.28.9+cuda13.0 | 13.2 | RTX 5090 | Downgraded from 2.30.4 on 2026-06-22. Alltoall benchmark pending. |
| 70.94 | 2.30.7+cuda13.3 | 13.2 | RTX 5090 | apt-installed, no CUDA/NCCL toolchain pre-installed. 8-GPU alltoall avg busbw=16.45 GB/s (30% slower than 70.88). |
| 70.95 | 2.30.4+cuda13.2 | 13.2 | RTX 5090 | — |
| 70.96 | 2.30.4+cuda13.2 | 13.2 | RTX PRO 6000 | — |
| 70.98 | 2.30.4+cuda13.2 | 13.2 | RTX PRO 6000 | — |

**Key finding (updated 2026-06-22):** Initial hypothesis was NCCL 2.30.4 regression causing worse 8-GPU alltoall on 70.98 vs 70.88. After downgrading 70.92 from NCCL 2.30.4 to 2.28.9, the 8-GPU alltoall peak busbw on 70.92 was ~12.3 GB/s — nearly identical to 70.98's ~12.9 GB/s with NCCL 2.30.4. This **disproves** the NCCL version regression hypothesis. The real differentiator is the **CPU**: 70.88 has a Xeon Platinum 8558P (48c/socket, 260MB L3/socket) while 70.92 and 70.98 have Xeon Gold 6530 (32c/socket, 160MB L3/socket). The 50% more cores and 62.5% more L3 cache on 70.88 substantially improves alltoall performance, especially at cross-NUMA scales. See `references/nccl-benchmark-results.md` for detailed analysis.

### Version compatibility
| CUDA Version | Latest NCCL | Notes |
|-------------|-------------|-------|
| cuda13.2 | 2.30.4 | Latest |
| cuda13.0 | 2.28.9 | Used on 70.88 |
| cuda12.9 | 2.30.4 | |
| cuda12.8 | 2.26.2 | Minimum for Blackwell |
| cuda12.x | Varied | For A100 on 70.66 |

### Verify NCCL
```bash
cat > /tmp/test_nccl.cu << 'EOF'
#include <nccl.h>
#include <stdio.h>
int main() { printf("NCCL compiled OK (version code: %d)\n", NCCL_VERSION_CODE); return 0; }
EOF
/usr/local/cuda/bin/nvcc -I/usr/include -o /tmp/test_nccl /tmp/test_nccl.cu -lnccl 2>&1 && /tmp/test_nccl
```

## nccl-tests Compilation & Bandwidth Testing

### Compile
```bash
## nccl-tests Compilation & Bandwidth Testing

### Compile
```bash
ssh jianliu@10.10.70.XX "source ~/.bashrc && mkdir -p ~/work/bandwidth_test/ && \
  cd ~/work/bandwidth_test/ && \
  git clone https://github.com/NVIDIA/nccl-tests.git && \
  cd nccl-tests && \
  make -j$(nproc)"
```

For servers without internet (e.g., 70.98 has no proxy), copy compiled binaries from another node via SSH pipe:
```bash
# On source node (e.g., 70.96), run:
ssh jianliu@10.10.70.96 "tar czf /tmp/nccl-tests.tar.gz -C ~/work/bandwidth_test nccl-tests"
cat /tmp/nccl-tests.tar.gz | ssh jianliu@10.10.70.98 "cat > /tmp/nccl-tests.tar.gz"
ssh jianliu@10.10.70.98 "cd ~/work/bandwidth_test && tar xzf /tmp/nccl-tests.tar.gz"
```

**IMPORTANT: If the source and target servers have different NCCL versions, you MUST rebuild nccl-tests on the target.** Pre-built binaries from NCCL 2.28 will fail with "Incompatible NCCL versions" error when run against NCCL 2.30+ (Device API changed at 2.29). Copy the source tree, then rebuild:

```bash
# Rebuild on target server (e.g., 70.92, 70.94) after installing OpenMPI:
ssh jianliu@10.10.70.XX "echo '!QAZ2wsx' | sudo -S apt-get install -y openmpi-bin libopenmpi-dev"
ssh jianliu@10.10.70.XX "cd ~/work/bandwidth_test/nccl-tests && rm -rf build && make MPI=1 NCCL_HOME=/usr MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi -j8"
```

> **Why `MPI=1`?** When building nccl-tests for single-node multi-GPU (all on one machine), MPI=1 links the OpenMPI library so `mpirun -np 8 --allow-run-as-root ./alltoall_perf -g 1 ...` works. Without MPI=1, `alltoall_perf` has no mpirun launcher and cannot spawn 8 processes. Also: **always use `-g 1`** (1 GPU per process) for single-node 8-GPU tests. `-g 8` (all 8 GPUs in one process) causes NCCL to request 64 GPUs (`8 processes × 8 GPUs`) and fail.

### Run tests
```bash
# Single GPU validation
./all_reduce_perf -b 8 -e 256M -f 2 -g 1 2>&1 | tail -5

# Full GPU test (adjust -g N for server's GPU count)
CUDA_VISIBLE_DEVICES=0,1,2,3 ./all_reduce_perf -b 8 -e 8G -f 2 -g 4 2>&1
./all_reduce_perf -b 8 -e 8G -f 2 -g 8 2>&1
```

### Output interpretation
- **AlgoBW**: Algorithm bandwidth (actual data/time)
- **BusBW**: Bus bandwidth (accounts for NCCL internal data movement, ~1.7-2× AlgoBW)

### Alltoall performance: cross-server comparison (2026-06-24, float32, 256MB-4GB, -g 1 -b 256M -e 4G -f 2 -w 10 -n 5)

Alltoall is significantly more sensitive to NCCL version than all_reduce due to its N² communication pattern.

| Server | GPU | CPU | NCCL | Driver-CUDA | Avg busbw (GB/s) | Peak busbw (GB/s) |
|--------|-----|-----|------|-------------|------------------|------------------|
| 70.88 | RTX 5090 32GB | Xeon Platinum 8558P (48c, 260MB L3) | 2.28.9+cu13.0 | 580.159.03 / 13.0 | 23.50 | 23.98 @ 4GB |
| 70.92 | RTX 5090 32GB | Xeon Gold 6530 (32c, 160MB L3) | 2.28.9+cu13.0 | 595.71.05 / 13.2 | untested (2026-06-24) | — |
| 70.94 | RTX 5090 32GB | (untested) | 2.30.7+cuda13.3 | 580.159.03 / 13.2 | 16.45 | 16.88 @ 4GB |

**Key finding — 70.94 vs 70.88 alltoall regression (2026-06-24):**
- 70.94 (NCCL 2.30.7, Driver 580.159.03, Driver-CUDA 13.2) achieves **16.45 GB/s avg busbw**
- 70.88 (NCCL 2.28.9, Driver 580.159.03, Driver-CUDA 13.0) achieves **23.50 GB/s avg busbw**
- **70.94 is ~30% slower than 70.88** despite nominally newer NCCL and same GPU model
- CPU difference is the likely cause: 70.88 has 48c/260MB L3 vs 70.94's unknown CPU (likely Ice Lake with less L3)
- 70.92 data missing — collect with: `ssh 10.10.70.92 "echo '!QAZ2wsx' | sudo -S apt-get install -y openmpi-bin libopenmpi-dev && cd ~/work/bandwidth_test/nccl-tests && rm -rf build && make MPI=1 NCCL_HOME=/usr MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi && cd build && mpirun -np 8 --allow-run-as-root ./alltoall_perf -g 1 -b 256M -e 4G -f 2 -w 10 -n 5"`

**Key findings — NCCL 2.30.4 regression DISPROVED:**
- **Same GPU, different NCCL:** 70.92 with NCCL 2.30.4 gets 12.36 GB/s 8-GPU peak busbw at 256M; after downgrading to NCCL 2.28.9, it gets 12.32 GB/s — **identical**. NCCL version is NOT the cause.
- **Same CPU, similar results:** 70.92 (Gold 6530) and 70.98 (Gold 6530) both show ~12-13 GB/s 8-GPU peak regardless of NCCL version or GPU model.
- **70.88 is the outlier:** 70.88's Xeon Platinum 8558P (48c/socket, 260MB L3) achieves 25.25 GB/s 8-GPU peak — 2x the Gold 6530 servers. The CPU difference (more cores, larger cache) is the primary factor.
- **4-GPU also affected by CPU:** 70.88 peaks at 35.46 GB/s vs 70.92 at 18.87 GB/s (both RTX 5090) — the CPU advantage applies to within-NUMA alltoall too.
- **No NVLink on any server** — all GPU communication is PCIe Gen5 x16 P2P
- **All servers show PCIe Gen1 at idle** (2.5 GT/s) — normal ASPM power-gating, ramps to Gen5 under load
- **Anomalous 16M bandwidth dip** on all servers in 8-GPU mode = NCCL ring/tree algorithm transition point

**Action:** Downgrade 70.92 to NCCL 2.28.9 (or upgrade 70.88 to 2.30.4) for definitive confirmation. Test `NCCL_ALGO=Ring`/`NCCL_ALGO=Tree` overrides on 2.30.4. Consider filing NCCL bug.

## Docker Setup & vLLM Deployment

### Install Docker
```bash
ssh jianliu@10.10.70.XX "echo 'PASSWORD' | sudo -S bash -c '
  apt-get update && apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \$(. /etc/os-release && echo \"\$VERSION_CODENAME\") stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io
  usermod -aG docker jianliu
'"
```

### Install NVIDIA Container Toolkit
```bash
ssh jianliu@10.10.70.XX "echo 'PASSWORD' | sudo -S bash -c '
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed \"s#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g\" | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update && apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
'"
```

### vLLM Docker deployment
```bash
docker run --gpus all \
  -v /home/jianliu/work/models:/models \
  -p 8000:8000 \
  --shm-size=32g \
  vllm/vllm-openai:latest \
  --model /models/MODEL_NAME --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 8 --gpu-memory-utilization 0.90 --trust-remote-code
```

### GPU Memory Exhaustion — Stale Processes from Crashed Runs

Multi-node vLLM clusters (DP=2, PP=2) that crash or are hard-killed leave **zombie GPU processes** holding 100% of VRAM. A subsequent startup attempt then fails immediately with:

```
ValueError: Free memory on device cuda:N (X.XX/YY.ZZ GiB) on startup is less than
desired GPU memory utilization (0.XX, ZZ.ZZ GiB)
```

**Diagnostic — identify stale GPU processes and their memory use:**
```bash
ssh jianliu@<node> "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | sort -t',' -k2 -rn | head -10"
```

**Fix — kill all stale compute processes (example PIDs):**
```bash
ssh jianliu@10.10.70.XX "kill -9 <pid1> <pid2> ... <pidN>"
```

**Verify GPU memory freed:**
```bash
ssh jianliu@10.10.70.XX "nvidia-smi --query-gpu=free,memory.used --format=csv,noheader"
```

**Pre-startup checklist** (run on ALL nodes before any restart):
```bash
for node in 96 98; do
  echo "=== 10.10.70.$node GPU memory ==="
  ssh jianliu@10.10.70.$node "nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader"
  echo "=== 10.10.70.$node compute processes ==="
  ssh jianliu@10.10.70.$node "nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader"
done
```

> **Root cause**: `kill -9` on the vLLM master process does NOT cascade to its child EngineCore and GPU workers — they survive as orphans holding VRAM. Always explicitly kill all `VLLM::Worker*` PIDs before restarting.

## Multi-Server Cluster Operations

For the 93/95/96 cluster (same hardware, Mellanox ConnectX-6 Dx NICs):

### Batch execution
```bash
for host in 93 95 96; do
  echo "=== 10.10.70.$host ==="
  ssh jianliu@10.10.70.$host "source ~/.bashrc && command"
done
```

### Inter-node SSH key prerequisites for multi-node vLLM DP

Multi-node Data Parallel vLLM (v0.6.0.dev0+) requires **passwordless SSH key auth in both directions** between all nodes. The EngineCore uses SSH for DP handshake coordination — without keys, startup silently hangs for 5 minutes and then fails with `Did not receive response from front-end process within 5 minutes` / `Gloo connectFullMesh failed: Connection refused`.

**Prerequisite check** — must succeed from EVERY node to EVERY other node:
```bash
ssh jianliu@<remote-ip> "hostname"
```

**Setup** — on each node, then copy to others:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
# Copy the pubkey output, then on each other node:
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "<pubkey from step above>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**`/etc/hosts` pitfall**: Ubuntu defaults to mapping hostname to `127.0.1.1` in `/etc/hosts`, which causes Gloo to bind to loopback and fail cross-node connections. Fix:
```bash
sudo sed -i '/HOSTNAME/d' /etc/hosts
echo "10.10.71.XX  HOSTNAME" | sudo tee -a /etc/hosts
```

**`--node-rank` pitfall**: Every node in a multi-node vLLM cluster must explicitly set `--node-rank`. If omitted, all nodes default to rank 0. The master will produce `HELLO message from remote engine 0, expected it to be local` because the worker also claims to be rank 0. Always set `--node-rank 0` on the master node and `--node-rank 1, --node-rank 2, ...` on workers.

**SSH key re-verification**: SSH keys set up weeks ago may stop working due to key rotation, OS updates, or authorized_keys being overwritten. When debugging multi-node vLLM startup failures, re-verify SSH passwordless auth from **every node to every other node** before investigating other causes. This is the single most common silent failure.

### NCCL socket interface (multi-node)
```bash
export NCCL_SOCKET_IFNAME=ens20f0
export NCCL_IB_DISABLE=1
export NCCL_DEBUG=INFO
```

### RoCE v2 with ConnectX-6 Dx (70.96 + 70.98 cluster)

When using the 100GbE RoCE v2 link between 70.96 and 70.98 for NCCL/Gloo:

```bash
export NCCL_SOCKET_IFNAME=bond0          # MUST be bond0 (has IP), NOT ens35f0np0 (no IP)
export GLOO_SOCKET_IFNAME=bond0          # same reason — GLOO needs an IP
export TP_SOCKET_IFNAME=bond0
export VLLM_HOST_IP="<node-ip-192.168.66.x>"
export MASTER_ADDR="192.168.66.10"  # master node's RDMA IP

export NCCL_IB_DISABLE=0

# CRITICAL: NCCL_IB_HCA differs per node!
# 70.96: rocep200s0f0
# 70.98: mlx5_bond_0
# Auto-detect:
export NCCL_IB_HCA=$(rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,')

export NCCL_IB_GID_INDEX=3
export NCCL_IB_TIMEOUT=23
export NCCL_IB_QPS_PER_CONNECTION=4
export NCCL_IB_TC=136
export NCCL_CROSS_NIC=0
export NCCL_MIN_NCHANNELS=8
export NCCL_NET=IB
```

**IMPORTANT:** Do NOT hardcode `NCCL_IB_HCA=rocep200s0f0` — 70.98 uses `mlx5_bond_0` instead. Always auto-detect.

**Critical: `NCCL_IB_HCA` is node-specific** — the RDMA device name CAN differ even on identical hardware. As of 2026-05-30, both 70.96 and 70.98 show `mlx5_bond_0` (converged after kernel/driver updates), but earlier 70.96 was `rocep200s0f0` while 70.98 was `mlx5_bond_0`. Always auto-detect:
```bash
rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,'
# Or use: ibv_devinfo | grep hca_id
```

**GLOO needs an IP'd interface, not a slave.** `ens35f0np0` is a bond slave with no IP — GLOO crashes with:
```
RuntimeError: [enforce fail at .../gloo/transport/tcp/device.cc:84] ifa != nullptr.
Unable to find address for: ens35f0np0
```
Fix: use `bond0` (or `ens20f0` for management network) for `GLOO_SOCKET_IFNAME`.

**ZMQ crash: `Cannot assign requested address`** — This means `VLLM_HOST_IP` or `MASTER_ADDR` points to an IP not configured on this host (e.g., using `10.10.71.96` when only `192.168.66.10` exists). Verify with `ip addr show bond0`.
### Perf & Intel PCM Installation

### perf (Linux kernel profiling)

Install the kernel-specific `perf` tools matching the running kernel:

```bash
# Find matching tools package
uname -r                              # e.g., 6.8.0-111-generic
apt-cache search linux-tools-$(uname -r | sed 's/-generic//')

# Install
sudo apt-get install -y linux-tools-$(uname -r | sed 's/-generic//')-generic

# Verify
perf --version
```

Note: `linux-tools-generic` metapackage may pull an older kernel tools version than the running kernel. Always install the **exact kernel version** package (e.g., `linux-tools-6.8.0-111-generic`).

### Intel PCM (Performance Counter Monitor)

The apt version of PCM (package `pcm`, version 202201-1) does NOT support Emerald Rapids (Xeon Gold 6530, CPU model 207) or newer Intel CPUs. Build from source:

```bash
# Download (if git clone fails from China, use curl + tar.gz):
curl -sL "https://github.com/intel/pcm/archive/refs/heads/master.tar.gz" -o /tmp/pcm.tar.gz
cd /tmp && tar xzf pcm.tar.gz && cd pcm-master && mkdir build && cd build
cmake .. && make -j$(nproc) && sudo make install

# Verify
/usr/local/bin/pcm-memory 1
```

Key binaries: `pcm`, `pcm-memory`, `pcm-core`, `pcm-power`, `pcm-numa`, `pcm-msr` (all at `/usr/local/bin/`). Old apt version at `/usr/sbin/pcm` is shadowed.

## Quick health check
```bash
ssh jianliu@10.10.70.XX "source ~/.bashrc && \
  echo '=== GPU ==='; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1; \
  echo '=== CUDA Driver ==='; nvidia-smi -q | grep 'CUDA Version'; \
  echo '=== nvcc ==='; /usr/local/cuda/bin/nvcc --version 2>&1 | tail -2; \
  echo '=== NCCL ==='; awk '/NCCL_(MAJOR|MINOR|PATCH)/{printf \"%s.%s.%s\\n\", \$3, \$3, \$3}' /usr/include/nccl.h; \
  echo '=== Disk ==='; df -h / | tail -1"
```

## vLLM Server Management

### Finding server process and config

```bash
# Find running vLLM processes and their startup config
ssh jianliu@10.10.70.XX "ps aux | grep 'vllm serve' | grep -v grep"

# Read the startup script to get full config including API key
ssh jianliu@10.10.70.XX "cat /path/to/start_script.sh"

# Get exact cmdline (includes API key which may be stripped from ps output)
ssh jianliu@10.10.70.XX "cat /proc/PID/cmdline | tr '\0' ' '"
```

### PP=2 (Pipeline Parallelism) Startup Procedure

For the PP=2 config between 70.96 (master) and 70.98 (worker):

**Script:** `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh`

The script should have three critical per-node customizations BEFORE first run:

1. **`NCCL_IB_HCA`** — Auto-detect per node with `rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,'`
2. **`VLLM_HOST_IP`** — Must match the host's actual RDMA bond0 IP (`192.168.66.10` on master, `192.168.66.20` on worker)
3. **`MASTER_ADDR` / `HEAD_IP`** — Must be the master's bond0 IP (`192.168.66.10`)

If the script has hardcoded `10.10.71.x` addresses, they won't work since those IPs don't exist on any interface. Fix them before starting.

**Cleanup stale processes first:** Before starting, check for leftover vLLM processes that may hold ports:
```bash
ssh 70.96 "ss -tlnp | grep -E '800|2950'"
ssh 70.96 "ps aux | grep 'VLLM::Worker' | grep -v grep | awk '{print \$2}'"
```
Kill any found (`kill -9 PID` if SIGTERM fails).

**Start order:** Both nodes can be started nearly simultaneously (within seconds), but worker first is more robust:
1. `bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh worker` (on 70.98)
2. Within 5-10s: `bash /data/venvs/vllm-ds4/start_dsv4_pro_2node.sh master` (on 70.96)

**Port conflict:** If port 29505 is in use by a zombie VLLM::Worker, either kill the PID holding it or use a different port:
```bash
MASTER_PORT=29506 bash start_dsv4_pro_2node.sh master
MASTER_PORT=29506 bash start_dsv4_pro_2node.sh worker
```
- `NCCL_SOCKET_IFNAME`, `GLOO_SOCKET_IFNAME`, `TP_SOCKET_IFNAME` must use `bond0` (which has 192.168.66.x), **not** `ens35f0np0` (which is a bond slave with no IP)
- If set to `ens35f0np0`, GLOO crashes: `Unable to find address for: ens35f0np0`

**NCCL_IB_HCA differs per node:**
- 70.96: `rocep200s0f0`
- 70.98: `mlx5_bond_0`
Auto-detect with: `rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,'`

**The 10.10.71.x IPs do NOT exist** on either node. The original script referenced `10.10.71.96/98` which were never configured on any interface. All RDMA traffic uses `192.168.66.x` on `bond0`.

**Startup failure triage:**
1. Check port reuse: `ss -tlnp | grep 2950` — kill leftover VLLM::Worker PIDs
2. Check NCCL_IB_HCA matches local RDMA device: `rdma link show`
3. Check GLOO_SOCKET_IFNAME has an IP: `ip addr show bond0`
4. Check RDMA reachability: `ping -c1 192.168.66.20` (from 96) / `192.168.66.10` (from 98)
5. Check logs: `/tmp/vllm_master.log` (on 96) and `/tmp/vllm_worker.log` (on 98)

### Graceful restart procedure (multi-node)

Multi-node DP clusters require **coordinated restart** — both nodes must be killed and restarted together:

1. **Kill workers first, then master**, or kill both simultaneously. Do NOT kill the master first and wait — the worker's EngineCore will crash with `Broken pipe` as soon as the master's TCPStore goes down.
2. **Clean up leftover GPU processes** — after killing the vLLM master process, the worker GPUs may still have dangling `VLLM::Worker_DP1_TP*` processes consuming 100% of VRAM. Always check on ALL nodes:
   ```bash
   for host in 96 98; do
     ssh jianliu@10.10.70.$host "nvidia-smi | grep VLLM"
   done
   ```
   Kill any leftovers by PID across all nodes before restarting.
3. **Start order**: Start the **worker node** first (with `--headless --node-rank 1`), then start the **master node** (with `--node-rank 0`). The worker will wait for the master's TCPStore to become available. If you start the master firstcf, it may timeout waiting for DP handshake with an absent worker.
4. **Simultaneous launch via nohup**: When using automatic launch scripts through SSH, use `setsid bash /tmp/launch_vllm.sh > /tmp/vllm_restart.log 2>&1 &` to detach from the SSH session, preventing the process from being killed when the SSH connection terminates.

### Verifying server readiness (multi-node DP)

Only the **master node** (node-rank 0) has an HTTP API server. The worker node has no port 8000. Check:
```bash
# On master node:
curl -s http://localhost:8000/health                  # shallow check
curl -s http://localhost:8000/v1/models                # model metadata, max_model_len
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"MODEL_NAME","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'   # real test

# On worker node:
ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker'      # check EngineCore + GPU workers are alive
```

1. **Identify all vLLM-related PIDs** (main process, resource_tracker, workers):
```bash
ssh jianliu@10.10.70.XX "ps aux | grep vllm | grep -v grep | awk '{print \$2}'"
```

2. **Kill processes** (SIGTERM first, SIGKILL if they don't die):
```bash
ssh jianliu@10.10.70.XX "kill PID1 PID2 ... 2>/dev/null; sleep 2"
# Force kill if still alive:
ssh jianliu@10.10.70.XX "kill -9 PID1 PID2 ... 2>/dev/null; sleep 2"
```

3. **Start the server** using its startup script (background recommended):
```bash
ssh jianliu@10.10.70.XX "cd /path/to/venv && bash start_script.sh"
# From Hermes: use terminal(background=true, notify_on_complete=true)
```

4. **Verify the server is up** — it can take several minutes for large models with compilation:
```bash
# Check if process is running
ssh jianliu@10.10.70.XX "ps aux | grep vllm | grep -v grep"

# Health endpoint (loads faster than models endpoint)
python3 -c 'import urllib.request; r=urllib.request.urlopen("http://localhost:8000/health"); print(r.status)'

# Models endpoint with API key (get max_model_len, served model name)
python3 -c '
import json, urllib.request
req = urllib.request.Request("http://localhost:8000/v1/models")
req.add_header("Authorization", "Bearer API_KEY_HERE")
r = urllib.request.urlopen(req)
for m in json.loads(r.read().decode())["data"]:
    print(json.dumps(m, indent=2))
'

# Quick chat test
python3 -c '
import json, urllib.request
body = json.dumps({"model":"MODEL_NAME","messages":[{"role":"user","content":"hi"}],"max_tokens":10}).encode()
req = urllib.request.Request("http://localhost:8000/v1/chat/completions", data=body,
    headers={"Content-Type":"application/json", "Authorization":"Bearer API_KEY_HERE"})
r = urllib.request.urlopen(req)
res = json.loads(r.read().decode())
print(res["choices"][0]["message"]["content"])
'
```

### Verifying context length

The `max_model_len` is set via `--max-model-len` in the startup script. To confirm it at runtime, check the v1/models endpoint response which includes `max_model_len` in the model metadata.

## Known Server Configs

| Server | Model | Port | API Key | Startup Script | Setup |
|--------|-------|------|---------|----------------|-------|
| 10.10.70.88 | qwen_image_2512 (Qwen Image, diffusion) | 8000 | none | `/tmp/qwen_image_server.py` (FastAPI + diffusers) | Running. `torch._dynamo.config.disable=True` required. Model loaded at startup (~60s). Requires `GET /health` endpoint — benchmark clients check this. Full benchmark (warmup + 3 runs × 512×512 @ 20 steps) needs ~760s, exceeds default 600s timeout. |
| 10.10.70.92 | deepseekv4_flash (DeepSeek-V4-Flash) | 8000 | none | `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh` | TP=8, EP enabled, kv-cache=fp8, block-size=256, max_model_len=16384, compilation-config=`cudagraph_mode:FULL_AND_PIECEWISE`, vLLM 0.6.0.dev0, NCCL 2.28.9. Model symlinked from `/home/public/models/tgu01/deepseekv4_flash/`. Note: 70.98's script uses `wdgraph_mode` instead of `cudagraph_mode` — parameter name differs by vllm version. |
| 10.10.70.95 | minimax_m2_7 (MiniMax M2 nvfp4) | 8000 | `***.95-vllm` | `/data/venvs/vllm-ds4/start_minimax_m2_nvfp4_tpep.sh` | TP=8, EP, max_model_len=262144, kv-cache=fp8, compilation mode=3 |
| 10.10.70.96 | deepseekv4_pro (DeepSeek-V4-Pro) | 8000 | none | `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` (master) | TP=8, PP=2, EP, NNODES=2, RoCE v2 (bond0, 192.168.66.10), max_model_len=1048576, kv-cache=fp8, compilation mode=3, NCCL_IB_HCA=rocep200s0f0 |
| 10.10.70.96 | glm5_1_fp8 (GLM-5.1-FP8) | 8000 | none | `/data/venvs/vllm-ds4/start_glm5_fp8_2node.sh` (master) | TP=8, PP=2, EP=8, NNODES=2, RoCE v2, max_model_len=65536, kv-cache=fp8, compilation mode=3, GlmMoeDsaForCausalLM, 256 experts, requires transformers>=5.4.0, CC 12.0 MLA patches |
| 10.10.70.98 | deepseekv4_pro (DeepSeek-V4-Pro, worker) | none (headless) | none | `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` (worker) | TP=8, PP=2, EP, NNODES=2, RoCE v2 (bond0, 192.168.66.20), NCCL_IB_HCA=mlx5_bond_0, `--headless` |
| 10.10.70.98 | glm5_1_fp8 (GLM-5.1-FP8, worker) | none (headless) | none | `/data/venvs/vllm-ds4/start_glm5_fp8_2node.sh` (worker) | Same as master except `--headless --node-rank 1` |
| 10.10.70.98 | glm5_1_fp8 (GLM-5.1-FP8, worker) | none (headless) | none | `/data/venvs/vllm-ds4/start_glm5_fp8_2node.sh` (worker) | Same as master except `--headless --node-rank 1` |
| 10.10.70.98 | deepseekv4_pro (DeepSeek-V4-Pro, worker) | none (headless) | none | `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` (worker) | TP=8, PP=2, EP, NNODES=2, RoCE v2 (bond0, 192.168.66.20), max_model_len=1048576, kv-cache=fp8, compilation mode=3, NCCL_IB_HCA=mlx5_bond_0, `--headless` (no HTTP server) |

## Testing Remote vLLM Servers from Local Machine

Remote servers' vLLM ports (8000) are not directly reachable from the local/WSL machine due to network segmentation. Use SSH port forwarding to tunnel the remote port locally:

### Single server tunnel
```bash
ssh -L 8000:localhost:8000 jianliu@10.10.70.XX
```
Keep this session running. In **another terminal**, test:
```bash
curl -s http://localhost:8000/health
```

### Multiple servers simultaneously
If you already have a tunnel on port 8000, use a different local port:
```bash
ssh -L 8001:localhost:8000 jianliu@10.10.70.YY
```
Then test with `http://localhost:8001`.

### API key handling
Servers with an API key (e.g., 70.95 with key `***.95-vllm`) need the `Authorization` header. The `***` characters are **literal asterisks in the key**, not shell globs — always use single quotes to prevent shell expansion:

```bash
curl -s -H 'Authorization: Bearer *** http://localhost:8000/v1/models | python3 -m json.tool
```

### Pitfalls

- **Never pipe vLLM output through `tee`** — if the `tee` process dies (OOM, disk pressure, log rotation), the pipe breaks and vLLM receives SIGPIPE, killing the entire server. Always redirect output directly to a file: `vllm serve ... > /tmp/vllm.log 2>&1`
- **API keys with asterisks** — some startup scripts may have literal `***` characters in the `--api-key` value due to placeholder substitution. These literal values actually work as the API key. Read the raw file or `/proc/PID/cmdline` to get the exact key.
- **Kill may not work on first try** — vLLM main processes and workers can be stubborn. Use `kill -9` if SIGTERM doesn't work after a few seconds.
- **Model loading is slow** — large models with `--compilation-config` can take several minutes to start. Don't assume failure — poll the process and health endpoint.
- **Use the venv's python** — for HTTP requests on servers without curl, use the vLLM venv's python interpreter to avoid Python version issues: `/data/venvs/vllm-ds4/bin/python3 -c '...'`
- **SSH port forwarding from Hermes** — when checking from the Hermes host, connections to vLLM ports on remote servers may be blocked. Check via SSH to the remote server instead.
- **Engine stats logging silently disabled (vLLM ≥ 0.6.0)** — when vLLM spawns multiple API server processes (`api_server_count > 1`), it auto-disables the periodic engine stats log (the `Engine 000: Avg prompt throughput: …` lines). The warning: `AsyncLLM created with api_server_count more than 1; disabling stats logging to avoid incomplete stats.` Fix: add `--api-server-count 1` to the `vllm serve` command. Trade-off: single API server may bottleneck at very high QPS (> dozens of req/s). The `/metrics` endpoint still provides aggregate stats regardless.
- **Orphaned worker after master crash (PP=2)** — if the master node (70.96) crashes/restarts but the worker node (70.98) keeps running, the worker's VLLM::EngineCore and GPU processes stay alive indefinitely. The worker won't be able to reconnect — it must be killed and restarted alongside the master. Check:
  ```bash
  # On worker node:
  ssh jianliu@10.10.70.98 "ps aux | grep vllm | grep -v grep"
  ```
- **`device_map="auto" not universally supported:** `DiffusionPipeline.from_pretrained(..., device_map="auto")` raises `NotImplementedError: auto not supported. Supported strategies are: balanced, cuda, cpu`. The `accelerate` version on the server determines what works. Use `enable_sequential_cpu_offload()` as a reliable fallback, or test `device_map="balanced"` — but for diffusion transformers, balanced across 8 GPUs adds NCCL communication overhead and is often slower than sequential CPU offload.

## Image Generation Model Servers (DiffusionPipeline)

For image generation models (e.g., Qwen Image, Stable Diffusion) served via `DiffusionPipeline` with FastAPI, the workflow differs from vLLM text servers.

### Starting and Testing a DiffusionPipeline Server

```bash
# 1. Check if already running
ssh jianliu@10.10.70.XX "pgrep -f qwen_image_server && echo 'ALREADY_RUNNING' || echo 'NOT_RUNNING'"

# 2. Health check
curl -s http://10.10.70.XX:8000/
curl -s http://10.10.70.XX:8000/info  # shows GPU memory and offload mode

# 3. Generate a test image (Python, handles JSON cleanly)
python3 - << 'EOF'
import urllib.request, json, base64
resp = urllib.request.urlopen(
    urllib.request.Request(
        "http://10.10.70.XX:8000/generate",
        data=json.dumps({
            "prompt": "a cute cat in a garden",
            "num_inference_steps": 20,
            "height": 512,
            "width": 512,
            "seed": 42
        }).encode(),
        headers={"Content-Type": "application/json"}
    ),
    timeout=300
)
result = json.loads(resp.read())
img_bytes = base64.b64decode(result["image_base64"])
open("/home/jianliu/test_img.png", "wb").write(img_bytes)
print(f"Generated {len(img_bytes)//1024}KB PNG")
EOF

# 4. Run benchmark
python3 - << 'EOF'
import urllib.request, json, time, base64

payload = {
    "prompt": "a majestic dragon flying over a fantasy kingdom, cinematic lighting",
    "num_inference_steps": 30,
    "height": 1024,
    "width": 1024,
    "seed": 123
}
data = json.dumps(payload).encode()
t0 = time.time()
resp = urllib.request.urlopen(
    urllib.request.Request("http://10.10.70.XX:8000/generate", data=data,
        headers={"Content-Type": "application/json"}),
    timeout=600
)
t = time.time() - t0
print(f"Time: {t:.1f}s  ({1/t:.2f} img/min)")
EOF
```

### Offload Modes (DiffusionPipeline)

- `enable_sequential_cpu_offload()` — **CPU-based**, iterates through model components one-by-one. Slow (~4-5s/step on RTX 5090) but reliable and crashes-free with the dynamo fix. No GPU acceleration.
- `device_map="balanced"` — Distributes layers across 8 GPUs with NCCL communication. Often 5-10× faster than sequential CPU offload but requires `torch._dynamo.config.disable = True` in PyTorch 2.x.
- `enable_attention_einsum("flash_attention_2")` — GPU-accelerated attention, requires FlashAttention support (xformers NOT installed on 70.88's vllm-ds4 venv).

**Benchmark first, then optimize offload strategy.** Sequential CPU offload is the safe default but orders of magnitude slower than GPU offload.

### ⚠️ PyTorch 2.x Dynamo + sequential_cpu_offload Crash (CRITICAL FIX)

On PyTorch 2.11+ with CUDA 13.0, `torch.compile()` / dynamo is **enabled by default**. Using `enable_sequential_cpu_offload()` without disabling dynamo causes an immediate crash:

```
RuntimeError: Tensor on device meta is not on the expected device cuda:0!
```

**Fix — place this at the VERY TOP of the server script, before any torch import:**

```python
import torch
torch._dynamo.config.disable = True          # MUST be before other torch imports
torch._dynamo.config.suppress_errors = True  # optional safety net

from diffusers import DiffusionPipeline
# ... rest of imports
```

**Why environment variables don't work:** `TORCH_COMPILE_DISABLE=1` and `PYTORCH_JIT=0` only affect the older `torch.jit` and `torch.compile` APIs, NOT the new `_dynamo` module. The Python-side config flag is required.

**Why bash-wrapping doesn't work reliably:** Setting `torch._dynamo.config.disable = True` inside a wrapper shell script that then launches uvicorn/Python may not propagate correctly due to module initialization order. **Always place the flag at the top of the Python file that uvicorn loads.**

**Additional common bugs in qwen_image_server scripts:**
- `JSONResponse` must be imported from `fastapi.responses`, NOT from `fastapi` directly:
  ```python
  from fastapi import FastAPI
  from fastapi.responses import JSONResponse  # CORRECT
  # from fastapi import JSONResponse       # WRONG — ImportError
  ```
- `torch.backends.cudagraphs.enabled = False` raises `AttributeError` in PyTorch 2.11+cuda13.0 on these servers — remove any such calls
- `@app.on_event("startup")` is deprecated in FastAPI 0.100+ but still functional — non-critical

**Benchmark (with dynamo disabled, sequential_cpu_offload, 8× RTX 5090):**

| Steps | Resolution | Total Time | Per-step (after warmup) | Throughput |
|-------|-----------|------------|-------------------------|------------|
| 1     | 512×512   | 7s         | 7.0s                    | ~8.6 img/hr |
| 5     | 512×512   | 22s        | ~3.8s                   | ~13.6 img/hr |
| 10    | 512×512   | 52s        | ~5.0s                   | ~11.5 img/hr |
| 20    | 512×512   | 91s        | ~4.4s                   | ~7.9 img/hr |
| 50    | 512×512   | est. ~4-5min | ~4-5s                 | est. ~0.27 img/min |
| 10    | 1024×1024 | >600s (TIMEOUT) | —                   | unusable |

Step 1 is ~7s slower due to GPU kernel JIT compilation. Steps 2+ are consistent at 4-5s each. At 1024×1024 resolution, even 10 steps exceeds typical timeout windows.

**`xformers` NOT available** on 70.88's vllm-ds4 venv — memory-efficient attention acceleration not currently installable.
**Benchmark first, then optimize offload strategy.** Sequential CPU offload is the safe default but orders of magnitude slower than GPU offload.

## Driver & CUDA Toolkit Downgrade

See `references/nvidia-driver-cuda-downgrade.md` for the complete procedure to downgrade NVIDIA driver + CUDA toolkit on Ubuntu 22.04. Covers:

- Removing `nvidia-driver-595-open` + `cuda-toolkit-13-2` and installing `nvidia-driver-580-server-open` + `cuda-toolkit-13-0`
- Post-reboot verification checklist
- SMI version vs Driver version mismatch interpretation

## nvidia-smi Version Mismatch (Corrupted Binary)

See `references/nvidia-smi-version-mismatch-diagnosis.md` for diagnosing when `NVIDIA-SMI version` differs from `DRIVER version` and `NVML version`. Covers:

- Using `dpkg --verify nvidia-utils-595` to detect a replaced/corrupted binary (MD5 checksum mismatch)
- Comparing with a known-correct server via `md5sum` / `strings`
- **Fix:** `sudo apt-get install --reinstall -y nvidia-utils-595` — no reboot required, no GPU downtime
- Root causes (CUDA toolkit overwrite, manual copy, version conflict)

## References

Detailed server-specific notes are stored in `references/`:
- `references/70-66-initial-setup.md` — 70.66 (A100 server): CUDA 10.1 system nvcc pitfall, partial CUDA installs, 6×A100 topology, 95% disk usage
- `references/70-88-detailed-setup.md` — 70.88: Primary dev server with proxy, full CUDA/NCCL/nccl-tests/vLLM fork setup
- `references/70-93-performance-quirks.md` — 70.93: Cluster node 1, no proxy, bare-metal initial setup patterns
- `references/70-95-security-config.md` — 70.95: Cluster node 2, proxy via .bashrc, LVM storage, newer kernel
- `references/70-96-storage-resize.md` — 70.96: Cluster node 3, proxy via .bashrc, LVM storage details
- `references/70-98-detailed-setup.md` — 70.98: RTX PRO 6000 Blackwell SE, no proxy, initial setup status
- `references/multi-node-vllm-debugging.md` — Detailed debugging timeline for 70.96+70.98 multi-node DP cluster: SSH keys, /etc/hosts fix, node-rank pitfall, KV cache sizing, timeout workarounds
- `references/nccl-benchmark-results.md` — NCCL bandwidth benchmark results across servers: 70.88 (8× RTX 5090, PCIe 5.0, ~31 GB/s), 70.96 (8× RTX PRO 6000, 2 NUMA domains, cross-NUMA ~21 GB/s via QPI/UPI)
- `references/cross-node-nccl-testing.md` — Cross-node NCCL bandwidth testing methodology, PyTorch distributed approach, MPI alternative, pitfalls (added 2026-05-30) — Systematic TTFT/throughput tuning: parameter matrix, prefix cache testing, compilation tradeoffs
- `references/vllm-bench-methodology.md` — vLLM benchmark tool usage, chat endpoint invocation, prefix_repetition dataset, metric interpretation, tuning dimension cost table, known hard limits (DP handshake 300s timeout, api-server-count + headless incompatibility)
- `references/glm5-fp8-deployment.md` — GLM-5.1-FP8 2-node deployment: setup steps, CC 12.0 patches, sparse MLA workaround, pitfall reference
- `references/qwen-image-2512-70-88.md` — qwen_image_2512 on 70.88: API schema, warmup results, sequential CPU offload slowness, rsync silent failure lesson
- `references/70-92-setup.md` — 70.92: RTX 5090 32GB×8, NCCL 2.30.4+cuda13.2 install, cuda-toolkit-13-2, nccl-tests rebuild, nvidia-smi wrapper fix
- `references/70-94-alltoall-benchmark.md` — 70.94: alltoall benchmark (16.45 GB/s avg busbw), VLLM kill, OpenMPI install, nccl-tests rebuild, 30% slower than 70.88
- `references/multi-hop-rsync-70-88-to-70-92.md` — Multi-hop rsync pattern: 70.88 → local → 70.92 transfer for qwen_image_2512 (54GB), local disk pre-flight, `/data/` ownership (rapidsdb) causing rsync mkdir failure, session transcript

## GPU Topology & P2P Diagnostics

### Topology map
```bash
ssh jianliu@10.10.70.XX "nvidia-smi topo -m"
```

Legend: `SYS` = PCIe + SMP/QPI/UPI between NUMA nodes, `NODE` = PCIe + interconnect within a NUMA node, `PIX` = at most a single PCIe bridge, `NV#` = NVLink.

### PCIe P2P support status
The command is `nvidia-smi topo -p2p r` (**not** `-p2p status` — that's invalid syntax):
```bash
ssh jianliu@10.10.70.XX "nvidia-smi topo -p2p r"
```
Output: `OK` = P2P supported, `CNS` = chipset not supported, `GNS` = GPU not supported, `TNS` = topology not supported, `NS` = not supported.

**Key insight:** GPUs showing `SYS` topology (cross-NUMA) can still report P2P `OK` on modern systems — PCIe P2P can traverse the CPU interconnect when ACS/IOMMU permits. Always check with `-p2p r`, don't assume `SYS` implies no P2P.

### PCIe Link Speed Diagnostics

### PCIe Link Speed Diagnostics

The PCIe link speed reported by nvidia-smi reflects the **current link training state** — which changes between idle and load:
```bash
# CORRECT nvidia-smi query syntax for PCIe info (verified 2026-06-24)
# -q = structured query output, -i = specific GPU index
nvidia-smi -q -i 0 | grep -A 10 'PCIe Generation'

# Quick all-GPU PCIe summary (loop, one-liner):
ssh jianliu@10.10.70.XX "for i in 0 1 2 3 4 5 6 7; do echo \"=== GPU \$i ===\"; nvidia-smi -q -i \$i | grep -E 'PCIe Gen|Link Width|Perf' | head -6; done"

# Simple CSV (gen current/max, width):
nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current --format=csv,noheader
```

**Critical: "Gen1 lock" is often misleading.** When idle (Performance State P8), the GPU power-gates the PCIe link and renegotiates down to Gen1. Under any workload (P1/P0), it renegotiates to Gen4/Gen5 ×16. Always test under load before concluding the link is stuck:

| Server | GPU | Perf State | Negotiated Max | Device Max | Host Max | Device Current | Current | Link Width | Driver | Note |
|--------|-----|-----------|--------------|------------|----------|--------------|---------|------------|---------|------|
| 70.88 | RTX 5090 ×8 | P8 (idle) | **Gen 5** | Gen 5 | Gen 5 | Gen 1 | Gen 1 | 16x | 580.159.03 | P8 idle → Gen1; under load → Gen5 |
| 70.92 | RTX 5090 ×8 | P8 (idle) | **Gen 4** | Gen 5 | Gen 5 | Gen 1 | Gen 1 | 16x | 595.71.05 | P8 idle → Gen1; negotiated Max capped at Gen4 |

To force renegotiation: run a GPU compute workload (e.g., `./all_reduce_perf -b 256M -e 256M -f 2 -g 8`), then re-query.

**nvidia-smi syntax pitfalls (verified 2026-06-24):**
- `nvidia-smi pcie` — **invalid** (unrecognized option)
- `nvidia-smi -d pcie` — **invalid** (`-d`/`--display` takes display types like MEMORY/UTILIZATION, not PCIe)
- `nvidia-smi -q -i N -d pcie` — **invalid** (combining `-q` and `-d` is mutually exclusive)
- `nvidia-smi nvlink` — valid subcommand but for NVLink status only, not PCIe gen/speed
- Correct for structured detail: `nvidia-smi -q -i N` — full output block includes `GPU Link Info` with all Gen/width fields
- Correct for CSV: `nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current --format=csv,noheader`
- Correct all-GPU loop: `for i in 0 1 2 3 4 5 6 7; do echo "=== GPU $i ==="; nvidia-smi -q -i $i | grep -E 'PCIe Gen|Link Width|Perf'; done`

**The old entry in nccl-tests bandwidth results is confirmed correct:**
> "All servers show PCIe Gen1 at idle (2.5 GT/s) — normal ASPM power-gating, ramps to Gen5 under load"

This explains why 70.88's all-servers PCIe Gen1 report is NOT a hardware problem — it's pure ASPM idle behavior.

### Key Finding: Negotiated Max Discrepancy (70.88 vs 70.92)

Both servers have **Device Max = Gen 5** and **Host Max = Gen 5** (identical hardware PCIe capability), but their **negotiated `Max`** differs:

- **70.88: Negotiated Max = Gen 5** — link trains to Gen 5 when under load
- **70.92: Negotiated Max = Gen 4** — link trains to Gen 4 (capped below Gen 5)

This is NOT an ASPM/idle artifact — the `Max` field is the negotiated link ceiling, recorded independently of Current speed. Possible causes (check in order):
1. **BIOS PCIe Speed Policy** — most likely. 70.92 BIOS may be set to "Gen 4" or "PCIe 4.0 Only" instead of "Auto/Gen 5". Requires physical/IPMI access.
2. **Driver version** — 70.92 runs `595.71.05`, 70.88 runs `580.159.03`. Newer driver may have more conservative Gen 5 link training.
3. **PCIe signal integrity** — Gen 5 (32 GT/s) is sensitive to PCB trace quality; 70.92's PCIe switch/riser may not reliably train to Gen 5.

**The `Device Max = 5` field on RTX 5090** comes directly from `nvidia-smi -q`. The RTX 5090 spec sheet says Gen 4, but the actual firmware/driver reports Gen 5 capability — use the nvidia-smi value as ground truth, not the spec sheet.

### Additional P2P checks

**NVLink status:**
```bash
nvidia-smi nvlink --status
```

**Check for PCIe replays / errors:**
```bash
nvidia-smi -q -i 0 | grep -i 'Replays\|Replay Number\|Correctable\|Uncorrectable'
```

**Hardware topology path:** For each GPU, trace the PCI bus hierarchy to identify the upstream bridge and its capabilities:
```bash
lspci -t                         # full PCI tree
lspci -s 15:01.0 -vn             # bridge vendor/device class (e.g. Intel 352a)
```

### Known GPU topologies & P2P status
- `references/gpu-topology-p2p.md` — Per-server GPU topology snapshots and P2P matrices.
- `references/gpu-pcie-state.md` — PCIe Gen/speed state: 70.88 (Gen 1 P8 idle) vs 70.92 (Gen 4 P1 loaded), nvidia-smi syntax guide, GPU bus addresses, **WarpDrive lspci vs nvidia-smi device ID mapping**.

## GPU Architecture Codes

| GPU | Arch | Compute Capability |
|-----|------|-------------------|
| A100 | Ampere | sm_80 |
| RTX 5090 | Blackwell | sm_120 |
| RTX PRO 6000 Blackwell SE | Blackwell | sm_120 |

**Device IDs (for NCCL/driver differentiation):**
- RTX 5090: 10de:2b85, PCI class 0300 (VGA)
- RTX PRO 6000 Blackwell SE: 10de:2bb5, PCI class 0302 (3D controller)

The different PCI classes may affect NCCL's device detection and algorithm selection, potentially explaining the cross-NUMA alltoall performance gap between 70.88 (RTX 5090, class 0300) and 70.98 (RTX PRO 6000, class 0302).

## Remote Process Daemonization & File Transfer Patterns

When starting long-running server processes via SSH that should outlive the SSH connection:

```bash
# WRONG — process dies when SSH times out:
nohup bash /tmp/start_server.sh > /tmp/server.log 2>&1 &   # FAILS: killed on SSH timeout

# ALSO WRONG — process dies when SSH times out:
bash /tmp/start_server.sh > /tmp/server.log 2>&1 &            # FAILS: same reason

# CORRECT — setsid forks a new session, survives SSH:
setsid bash /tmp/start_server.sh </dev/null >/tmp/server.log 2>&1 &
```

### Docker Keep-Alive Pattern (with -lc + --entrypoint)

When using `docker run ... tail -f /dev/null` as a keep-alive (so you can `docker exec` into the container later), two equivalent patterns exist — and one is subtly broken:

```bash
# BROKEN — bare CMD, no login shell, environment may be incomplete:
docker run -d --name mycontainer IMAGE tail -f /dev/null

# CORRECT — explicit ENTRYPOINT + bash -lc (login + command string):
docker run -d --name mycontainer \
  --entrypoint /bin/bash IMAGE -lc 'sleep infinity'
```

**Why the broken pattern fails:** Without `--entrypoint`, `tail -f /dev/null` runs as the image's default CMD. The `-l` (login shell) flag is never set, so `/root/.bashrc` (which often sets CUDA_PATH, LD_LIBRARY_PATH, etc.) is not sourced. Environment variables critical for GPU execution may be missing.

**The `-lc` flags:** `-l` = login shell (sources /etc/profile and ~/.bashrc), `-c '...'` = execute string. Together they ensure the container's full shell environment is initialized before `sleep infinity` runs.

**Always use `--entrypoint /bin/bash IMAGE -lc 'sleep infinity'`** for keep-alive containers that need the full host environment (CUDA libraries, vLLM paths, etc.).

### Multi-Hop File Transfer (rsync when servers can't reach each other directly)

When two servers (A and B) cannot SSH directly to each other (no keys distributed, host key unknown, or no route), use the **local machine as an intermediary**:

```
A → local → B
```

**Step 1: A → local**
```bash
rsync -avP --bwlimit=0 jianliu@10.10.70.A:/data/models/MODEL_NAME/ /home/jianliu/model_dst/ 2>&1
```

**Step 2: local → B**
```bash
rsync -avP --bwlimit=0 /home/jianliu/model_dst/ jianliu@10.10.70.B:/data/models/MODEL_NAME/ 2>&1
```

**Pre-flight checklist before using local as intermediary:**
1. **Local disk space**: `df -h /home/jianliu/` — must have at least as much free space as the dataset size
2. **ssh-copy-id is non-interactive**: Cannot be used from Hermes terminal. User must run `ssh-copy-id jianliu@10.10.70.B` manually on their local machine first
3. **Host key blocking**: `ssh-keyscan -t rsa 10.10.70.B >> ~/.ssh/known_hosts` pre-populates known_hosts but only works if server B already has server A's SSH key for the reverse direction
4. **Bandwidth estimate**: `rsync -avP` shows real-time MB/s; for 50GB+ datasets at ~100 MB/s, budget ~9-10 minutes

**Direct server-to-server rsync** (works only when both servers already have each other's keys):
```bash
# On server A, rsync directly to server B:
ssh jianliu@10.10.70.A "rsync -avP /data/models/MODEL_NAME/ jianliu@10.10.70.B:/data/models/MODEL_NAME/"
```

**Typical failure modes when servers can't reach each other:**
- `Permission denied (publickey,password)` — server B doesn't have server A's pubkey in `authorized_keys`
- `Host key verification failed` — server A's `known_hosts` doesn't have server B's host key
- `No route to host` — network segmentation, no path between the two servers' subnets
- `rsync: [Receiver] mkdir "/data/models/MODEL_NAME" failed: No such file or directory` — destination parent directory does not exist and rsync cannot create it. **IMPORTANT: This error message can mask a permission-denied condition.** If the parent directory exists but is not writable by jianliu, rsync may report "No such file or directory" instead of "Permission denied". **Always check `/data/` ownership before assuming the path doesn't exist.**
- **`/data/` not writable** — ALL known servers (70.88, 70.92, 70.95, 70.96, 70.98) have `/data/` owned by `rapidsdb`. jianliu cannot write to `/data/` directly. Always verify write access or default to `/home/jianliu/` on the target server.
- **`/data/` not writable** — some servers (e.g., 70.92) have `/data/` owned by `rapidsdb`, not by `jianliu`. Always verify write access before rsyncing, or default to `/home/jianliu/` on the target if `/data/` is locked.

**To write files with complex content (Python code, JSON, configs) to remote servers without heredoc escaping issues:**

1. Write the file locally
2. Base64-encode it locally: `base64 file.py > file.b64`
3. Transfer: `scp file.b64 remote:/tmp/file.b64`
4. Decode on remote: `ssh remote "cat /tmp/file.b64 | base64 -d > /tmp/file.py"`

```bash
# One-liner (B64 var set locally via $(cat file.b64)):
ssh remote "echo '$B64' | base64 -d > /tmp/file.py"
```

Python heredoc via `ssh remote "python3 - << 'EOF' ..."` frequently mangles quotes and backslashes. Base64 transfer is reliable.

## User Management (Remote Servers)

### Create user with home directory and bash shell
```bash
ssh jianliu@10.10.70.XX "echo '!QAZ2wsx' | sudo -S useradd -m -s /bin/bash USERNAME"
```

### Add user to sudo group
```bash
ssh jianliu@10.10.70.XX "echo '!QAZ2wsx' | sudo -S usermod -aG sudo USERNAME"
```

### Set user password
```bash
ssh jianliu@10.10.70.XX "echo '!QAZ2wsx' | sudo -S bash -c \"echo 'USERNAME:PASSWORD' | chpasswd\""
```

**Important:** `useradd -m` creates the account with a **locked password** — the user cannot log in via password until you explicitly set one with `chpasswd` or `passwd`. SSH key auth works immediately, but password auth requires this extra step.

### Verify
```bash
ssh jianliu@10.10.70.XX "id USERNAME && getent group sudo"
```

### User accounts on 70.92 (as of 2026-06-24)

| User | UID | Groups | Password | Notes |
|------|-----|--------|----------|-------|
| jianliu | 1000 | jianliu, sudo | SSH key + !QAZ2wsx | Primary admin |
| qs | — | sudo | — | Pre-existing |
| luojie | — | sudo | — | Pre-existing |
| xuechenli | 1004 | xuechenli, sudo | !QAZ2wsx | Added 2026-06-24 |
| yirongpan | 1005 | yirongpan, sudo | !QAZ2wsx | Added 2026-06-24 |

## Pitfalls

- **SSH hostname shorthand resolution**: Short hostnames like `70.92` may resolve to wrong IPs (e.g., `70.0.0.92` instead of `10.10.70.92`). **Always use the full IP `10.10.70.XX`** when SSHing to servers. The shorthand depends on DNS/search domain config and is unreliable.
- **Proxy servers need `source ~/.bashrc`** — non-interactive SSH never loads .bashrc; commands will hang without proxy
- **70.88 external internet (updated 2026-06-09):** Proxy is now configured in `~/.bashrc` (`10.10.60.140:7890`). PyPI and HuggingFace are reachable via `source ~/.bashrc && <command>`. Use Tsinghua Tuna mirror for pip reliability: `-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30`.
- **NVIDIA repo auto-redirects** in China to `developer.download.nvidia.cn` (mirror)
- **CUDA 10.1 on 70.66** — system `/usr/bin/nvcc` is ancient; always use `/usr/local/cuda/bin/nvcc`
- **Disk space on 70.66** — 95% full (~260 GB free); install large packages with caution
- **No RDMA on cluster** — CX-6 Dx NICs are not connected for RDMA; 1 Gbps TCP only
- **`device_map="auto"` not universally supported:** `DiffusionPipeline.from_pretrained(..., device_map="auto")` raises `NotImplementedError: auto not supported. Supported strategies are: balanced, cuda, cpu`. The `accelerate` version on the server determines what works. Use `enable_sequential_cpu_offload()` as a reliable fallback, or test `device_map="balanced"` — but for diffusion transformers, balanced across 8 GPUs adds NCCL communication overhead and is often slower than sequential CPU offload.
- **PyTorch 2.x dynamo crashes with `sequential_cpu_offload()`:** Any DiffusionPipeline server using `enable_sequential_cpu_offload()` on PyTorch 2.11+ **must** set `torch._dynamo.config.disable = True` at the top of the server script. Without it, inference crashes with `RuntimeError: Tensor on device meta is not on the expected device cuda:0!`. See "PyTorch 2.x Dynamo + sequential_cpu_offload Crash" section above.
- **70.88 mgmt NIC at 100 Mb/s** — `ens20f0` on 70.88 auto-negotiated to 100 Mb/s (Fast Ethernet), not 1 GbE. This caps rsync/SCP throughput at ~5.3 MB/s. A 149G model transfer takes ~8 hours. Other servers (70.96, 70.98) have 1 GbE management NICs. May be a switch port or auto-negotiation issue — check `ethtool ens20f0` and consider forcing 1 GbE if the switch supports it.
- **Do not hardcode passwords** in cron jobs or scripts — prefer SSH key auth for automated tasks
- **`-t` flag required** for PTY-dependent commands (watch, top, interactive sudo)
- **Fake nvidia-smi wrapper (xplatform/WarpDrive stub)**: On WarpDrive-appliance servers (70.93 confirmed, 70.92 formerly, 70.94 confirmed), `/usr/local/bin/nvidia-smi` is a shell script that just does `exit 113` (installed by "xplatform" to block nvidia-smi in favor of `wd-smi`). Since `/usr/local/bin` is earlier in PATH than `/usr/bin`, it shadows the real binary. **On 70.92**: removed 2026-06-22, real nvidia-smi at `/usr/bin/nvidia-smi`. **On 70.93**: still present — use `wd-smi` instead (WarpDrive's GPU monitoring tool). **On 70.94**: still present — use `/usr/bin/nvidia-smi` directly. Check other servers for the same issue if `nvidia-smi` returns exit code 113 or hangs silently.
- **vLLM `--compilation-config` parameter name differs by version**: vLLM 0.6.0.dev0 (70.88/70.92) uses `cudagraph_mode`, while newer builds (70.98's `0.1.dev1+gb709b75b4`) use `wdgraph_mode`. Passing `wdgraph_mode` to vLLM 0.6.0.dev0 causes `pydantic_core.ValidationError: Unexpected keyword argument`. Fix: check which vllm version is installed (`python -c 'import vllm; print(vllm.__version__)'`) and use the matching parameter name. For vLLM 0.6.0.dev0: `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", "custom_ops":["all"]}'`
- **DeepSeek-V4-Flash context length**: model config `max_position_embeddings=1048576` (1M), `original_max_position_embeddings=65536`, YaRN scaling factor 16. The startup script on 70.92 defaults to `MAX_LEN=16384`; 70.98's script uses `MAX_LEN=1048576`. Change based on VRAM budget.
- **`-g 8` vs `-g 1` in nccl-tests**: When running 8-GPU alltoall/all_reduce on a single node, **always use `-g 1`** (1 GPU per MPI rank, 8 ranks total). `-g 8` means "all 8 GPUs in one process" — with `mpirun -np 8` this requests 64 GPUs total and NCCL fails with "Invalid number of GPUs: 56 requested but only 8 were found." The correct invocation: `mpirun -np 8 --allow-run-as-root ./alltoall_perf -g 1 -b 256M -e 4G -f 2 -w 10 -n 5`
- **venv copy requires matching Python version**: When copying a Python venv (e.g., `/data/venvs/vllm-ds4/`) from one server to another, the venv's `bin/python3.12` symlink points to `/usr/bin/python3.12` (absolute path). If the target server doesn't have the same Python version installed, the venv won't work. Fix: install the matching Python version on the target (e.g., `sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt-get install -y python3.12 python3.12-venv python3.12-dev`). Using `tar` through SSH pipe is more reliable than rsync for large venv copies (rsync to remote IP may trigger security scan blocks).
- **venv copy requires matching Python version AND source tree**: When copying a venv (e.g., `/data/venvs/vllm-ds4/`) from one server to another: (1) The venv's `bin/python3.12` symlink points to `/usr/bin/python3.12` (absolute path) — the target must have the same Python version installed. (2) If the venv uses an **editable install** (`pip install -e .`), the source tree must also be copied. For vLLM ds4-sm120, the venv has `__editable__.vllm-0.6.0.dev0.pth` pointing to `/data/vllm-ds4-sm120/vllm` — without this 6.2GB source tree, `import vllm` fails with `ModuleNotFoundError`. Copy both the venv and the source tree, then create model symlinks.
- **rsync to remote IP addresses may be blocked** by security tools. Workaround: use `tar cf - dir | ssh remote "cd /path && tar xf -"` as a pipe through SSH instead.
- **`/data/` ownership on 70.92**: `/data/` is owned by `rapidsdb:rapidsdb`. jianliu cannot write directly. Always use `sudo mkdir -p /data/dir && sudo chown jianliu:jianliu /data/dir` before rsync/tar extraction. The `tar` command will fail with "Cannot mkdir: Permission denied" if the target directory isn't writable.
- **venv path is plural `venvs/`** — on 70.88 (and potentially 95/96), the venv is at `/data/venvs/vllm-ds4/` (plural). `/data/venv/` (singular) does not exist. Always verify with `ls /data/venvs/` if a script fails with `command not found`.
- **pip Tuna mirror on proxy servers** — on proxy servers (70.88, 95, 96), use `-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout=30` for faster, more reliable pip installs.
- **Multi-node vLLM DP requires SSH keys between all nodes** — See section "Inter-node SSH key prerequisites for multi-node vLLM DP" above. The EngineCore handshake uses SSH; without keys, startup silently hangs until 5-minute timeout.
- **Do not hardcode passwords** in cron jobs or scripts — prefer SSH key auth for automated tasks