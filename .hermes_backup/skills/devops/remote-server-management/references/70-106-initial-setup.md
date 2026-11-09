# 10.10.70.106 (oemp106) — Initial Discovery (2026-09-01)

New 8× RTX 6000D node, sibling of oemp107. Discovered live from WSL via pexpect SSH (jianliu / !QAZ2wsx).

## Hardware

| Item | Value |
|------|-------|
| Hostname | oemp106 |
| Chassis | (same BI5284-class as 107; ASPEED BMC VGA 1a03:2000) |
| GPU | 8× NVIDIA RTX 6000D, PCI `10de:2bb9` rev a1 (3D controller 0302), 85,651 MiB each |
| CPU | 2× Intel Xeon Gold 6530 (32c/socket), 128 threads |
| RAM | 1.0 TiB (950G available at discovery) |
| Root disk | 893.8G sda → LVM `ubuntu--vg-ubuntu--lv` 100G mounted `/` (61G used, 65%) |
| NVMe | 2× 3.5T (`nvme0n1`, `nvme1n1`) → LVM `datavg-datalv` 7T mounted **/home** (66G used) |
| NIC mgmt | `enx6c1ff7ed288b` 10.10.70.106/24 UP; `enx8653a81c20b1` DOWN |
| NIC cluster | `bond0` (ens21f0np0 + ens21f1np1, LACP) 10.10.68.106/23 UP |
| RDMA | `ibs35` (ConnectX) DOWN — same as delivered state on 107 before OFED setup |

## Software

| Item | Value |
|------|-------|
| OS | Ubuntu 22.04.4 LTS, kernel 5.15.0-190-generic |
| Driver | NVIDIA UNIX **Open** Kernel Module 610.43.02 (built 2026-05-19) — `nvidia-smi` works |
| Docker | 29.7.2, overlay2, root dir `/home/docker`; jianliu in `docker` group (uid 1005) + `sudo` |
| nvidia-container-toolkit | 1.20.0 (nvidia-ctk present) |
| Proxy | none |
| SSH | password-only (jianliu/!QAZ2wsx, sudo same); **no ~/.ssh at all** → no GitLab key on this node |

## NFS storage

- `/modelzoo` = `10.10.68.79:/modelzoo` — **28T, 5.2T used** (note: 107's /modelzoo is `10.10.68.71:/data` 14T — different NFS source!). Contents: deepseekv4_flash, deepseekv4-flash-0731 (156G, owner luojie), DeepSeek-V4-Flash-Vision-Exp, deepseekv4_pro, deepseekv4_pro_0813, glm_5_2_nvfp4, glm_5_3_flash_fp8 (owner panyirong, Aug 31), Kimi-K3, MiniMaxAI, minimax_m2_7_nvfp4, Qwen3-8B, Qwen3.5-9B, Qwen3.6-35B-A3B-FP8, Qwen3.6-35B-A3B-NVFP4, qwen_image_2512, stable-diffusion-2-base, wan2.2_t2v_A14B.
- `/userdata` = `10.10.68.71:/data` — 14T, 5.0G used. Top level: config_file, dataset, jianliu/, luojie/, xiaqing/.

## Docker images present

- `kimi-k3:tp8-pp3-20260818-mamba-indexfix-20260828` (25.9GB)
- `kimi-k3:tp8-pp3-20260818-profiler-sm120` (28.4GB)
- `kimi-k3:tp8-pp3-20260818` (25.9GB)
- `10.10.91.56/sw2/kimi-k3:tp8-pp3-20260818` (25.9GB)
- `10.10.91.56/sw2/vllm/vllm-openai:kimi-k3` (25.9GB)
- `10.10.91.56/sw2/fathomless-main-verify:gpu-smoke-fix6` (33.8GB)

## Running container

`dspark-v9-hybrid-fix6-180k` (host net, all GPUs): DeepSeek-V4-Flash-DSpark vLLM 0.11.2.dev280+fathomless cu132, port 8001, TP=8, DSpark speculative (5 tokens, probabilistic), kv fp8, max_model_len 262144, FULL_AND_PIECEWISE, FLASHINFER_MLA_SPARSE_DSV4, async-scheduling, prefix caching. Model = /modelzoo/deepseekv4-flash-0731. Overlays bind-mounted from /home/xiaqing/tgu01_pro/tgu01-pro-model-deployment/deepseekv4_flash/overlays/vllm-hybrid-speculator/. GPU memory ~76.5GB/GPU in use.

## Differences vs oemp107 (10.10.70.107)

| Aspect | 106 | 107 |
|--------|-----|-----|
| Reachable from WSL | YES (direct SSH) | No — via jump host 70.96 |
| /modelzoo source | 10.10.68.79:/modelzoo (28T) | 10.10.68.71:/data (14T) |
| /userdata | 10.10.68.71:/data | (NFS also present) |
| ~/.ssh / GitLab key | absent | present (@liujian) |
| Kernel | 5.15.0-190 | 5.15.0-119 |
| Workload | DSpark DS-V4-Flash (xiaqing/qs, port 8001) | PD disaggregation test env (jianliu) |

## Quick commands

```bash
# From WSL
python3 ~/.hermes/skills/devops/remote-server-management/scripts/pexpect-ssh.py 10.10.70.106 jianliu '!QAZ2wsx' '<cmd>' 30
python3 ~/ssh106.py '<cmd>'            # equivalent local helper

# GPU fleet
... 'nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv,noheader'

# Service health
... 'curl -s -m 5 http://localhost:8001/v1/models | head -c 300'
```
