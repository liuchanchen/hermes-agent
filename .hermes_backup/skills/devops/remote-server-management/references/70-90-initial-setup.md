# 10.10.70.90 (warp-Bumblebee-BI5284) — 2× RTX PRO 6000 Blackwell SE

## Hardware

| Attribute | Value |
|-----------|-------|
| Vendor | WARPDRIVE |
| Model | Bumblebee BI5284 |
| GPU | **RTX PRO 6000 Blackwell SE** × **2** (PCI ID `10de:2bb9` — only 2 GPUs, not 8 like other nodes) |
| GPU BAR | 2 × 128G BAR per GPU (prefetchable) |
| CPU | **Intel Xeon Platinum 8558P** (48c/socket, 260MB L3 — best CPU in cluster, same as 70.88) |
| RAM | 125 GiB total |
| System Disk | 1.7 TB (sda3, ext4, `/`) |
| Data Disk | **7 TB NVMe** (nvme0n1, ext4 → `/data`) — largest NVMe in the cluster |
| Mgmt NIC | ens20f0 — 10.10.70.90/24, gateway 10.10.70.254 |

## Software

| Component | Version |
|-----------|---------|
| OS | Ubuntu 22.04.5 LTS |
| Kernel | 6.8.0-124-generic |
| NVIDIA Driver (kernel) | **595.71.05** (Open Kernel Module) |
| NVIDIA Library | **595.84** (mismatch — reboot required) |
| CUDA (NVML) | **13.3** (from libnccl2) |
| NCCL | **2.30.7-1+cuda13.3** |
| Docker | Compose v5.1.1 |
| Registry | `10.10.91.56` (private), `qsharbor.warpdriveai.com`, `192.168.12.12:5000` |
| Docker mirrors | docker.1ms.run, mirror.aliyuncs.com, docker.mirrors.ustc.edu.cn |

## Key Differences from Other Nodes

| Aspect | Other TGU/Blackwell nodes | 70.90 |
|--------|--------------------------|-------|
| GPU count | 8× | **2× RTX PRO 6000 Blackwell SE** |
| CPU | Gold 6530 | **Platinum 8558P** (48c, 260MB L3) |
| NVMe size | 3.5 TB | **7 TB** |
| NVIDIA driver | Various | 595.71.05 kernel / 595.84 lib — **mismatch** |
| jianliu password | !QAZ2wsx | **jianliu/!QAZ2wsx SSH confirmed working (2026-08-03)** — previously only qs had working password auth |
| Reboot required | No | **Yes** — `/var/run/reboot-required` |

## GPU Discovery

```
98:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:2bb9] (rev a1)
d8:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:2bb9] (rev a1)
```

Only 2 GPUs. Both RTX PRO 6000 Blackwell SE (10de:2bb9 — same as 70.96/70.98). No GPU 0 here (bus numbering starts at 98:). Total GPUs occupies 2 of 8 possible slots.

## Driver/Library Mismatch

- **Kernel module** (loaded): 595.71.05 — from driver .ko
- **NVML library** (installed): 595.84 — from `libnvidia-compute-595`
- **Result**: `nvidia-smi` fails with "Failed to initialize NVML: Driver/library version mismatch"
- **Fix**: Reboot the server to reload kernel module matching library version
- `/var/run/reboot-required` exists (Linux package updated 2026-07-28)

## Docker Registry & Images

Private registry at `10.10.91.56` hosts WarpDrive vLLM images:

| Image | Tag | Size | Notes |
|-------|-----|------|-------|
| vllm-openai | nightly | 20.3GB | Standard nightly |
| vllm-warpdrive-release-ubuntu-22.04-amd64 | 0.9.0-release-0.0.1 | 14.9GB | WarpDrive release |
| vllm-warpdrive-release-ubuntu-22.04-amd64 | 0.10.1-release-0.0.6 | 14.3GB | Latest release |
| vllm-warpdrive-release-ubuntu-22.04-amd64 | latest | 14.3GB | |
| vllm-warpdrive-release-ubuntu-22.04-amd64 | test | 14.3GB | |
| vllm-tt-metal-src-release-ubuntu-22.04-amd64 | 0.9.0-... | 12.4GB | TT-Metal source |

## Available Models

Models stored at `/data/home/public/models/tgu01/`:
- `gemma-4-31B-it`
- `Qwen3-32B`
- `Qwen3.6-35B-A3B-FP8`
- `Qwen3.6-35B-A3B-NVFP4`
- `Qwen3-8B`

## Users

System has 15+ user accounts including: jianliu (uid 1006, sudo, docker), qs (uid 1001, sudo, docker), liuchao, luojie, wangdongyang, wanglei, warp, xiaqing, xiayuhang, xuechenli, yirongpan, yupengli, zhangzezhong, zhaojianling.

## /etc/hosts

Standard Ubuntu: `127.0.1.1 warp-Bumblebee-BI5284` — Gloo pitfall if used in multi-node.

## Current Status

- No vLLM containers running (docker ps empty)
- NVML driver/library mismatch — nvidia-smi non-functional
- **Docker image `vllm/vllm-openai:nightly` (20.3 GB) loaded (2026-08-03)** — ready for vLLM deployment
- Excellent hardware for testing/tuning: fast CPU (8558P), large NVMe (7TB), 2 GPUs good for small-scale PP/TP experiments
- Good candidate for vLLM development/testing with WarpDrive custom images

## Quick Reference

```bash
# Connect via qs (password works)
cd ~/.hermes/skills/devops/remote-server-management && \
  python3 scripts/pexpect-ssh.py 10.10.70.90 qs '!QAZ2wsx' 'hostname' 20

# Check NVML mismatch status
python3 scripts/pexpect-ssh.py 10.10.70.90 qs '!QAZ2wsx' 'nvidia-smi' 10

# List models
python3 scripts/pexpect-ssh.py 10.10.70.90 qs '!QAZ2wsx' 'ls /data/home/public/models/tgu01/' 10

# Run a test container from private registry
python3 scripts/pexpect-ssh.py 10.10.70.90 qs '!QAZ2wsx' \
  'docker run --rm --gpus all 10.10.91.56/sw2/vllm/vllm-openai:nightly nvidia-smi' 30
```
