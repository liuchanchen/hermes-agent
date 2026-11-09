---
name: remote-server-70-107
description: Access oemp107 (10.10.68.107) 8x RTX 6000D Blackwell node.
version: 0.1.0
author: Hermes Agent
license: Proprietary
platforms: [linux]
metadata:
  hermes:
    tags: [GPU, RTX6000D, Blackwell, Remote, Server, WarpDrive, RDMA]
---

# Remote Server 10.10.68.107 (oemp107)

Access and management for server `oemp107` at `10.10.68.107` with **8× NVIDIA RTX 6000D** GPUs (Blackwell GB202, compute capability 12.0 / sm_120). Reachable from jump host `10.10.68.96` on the same subnet.

**This is a 68-net cluster member** — dual-homed: management on `10.10.68.107/24`, cluster/storage on `10.10.68.107/23` (bond0, 25Gbps LACP). The box is now **fully provisioned**: NVIDIA driver + Docker + docker group for jianliu are all in place (as of 2026-08-25).

## When to Use

- "Log in to 10.10.68.107 / oemp107"
- "What GPU does the 107 server have?" (8× RTX 6000D)
- "Check disk/memory on 107"
- "What's on /modelzoo?"
- Setting up a new node in the 68-net cluster (driver, docker, RDMA)

## ⚠ ACCESS RESTORED (2026-09-04) — direct from WSL, no jump host needed

New credentials (old `jianliu`/`!QAZ2wsx` password auth stopped working 2026-09-03):
`liujian` / `985202Qs~`. Works DIRECTLY from WSL (10.10.x network reachable without
the 96 jump host) via the pexpect helper:

```bash
python3 ~/.hermes/skills/devops/remote-server-management/scripts/pexpect-ssh.py \
  10.10.68.107 liujian '985202Qs~' 'hostname' 40
```

Verified live 2026-09-04: oemp107 up, 8× RTX 6000D, nvidia-smi query + compute-apps OK
(VLLM workers running). **`liujian` now HAS sudo** (added via `qs`/`!QAZ2wsx`, same
pattern: `echo <b64> | base64 -d | sudo -S cmd` — avoids bash history `!` expansion).
Jump-host route below still works as fallback.

## Prerequisites

- **Jump host (fallback)**: `10.10.68.96` (key auth or password `!QAZ2wsx`). Has `sshpass` 1.09.
- **Credentials (primary, 2026-09-04)**: `liujian` / `985202Qs~` — direct SSH from WSL.
  Old `jianliu` account was DELETED from the box (verified 0904: no such user, home
dir removed) — password auth did not "break", the account is gone. No local sudo
account remains accessible to us.
- **Network**: Management NIC `enx9c69d373a98b` at `10.10.68.107/24`, default gw `10.10.69.254`. Cluster NIC is `bond0` (ens21f0np0 + ens21f1np1, 802.3ad LACP, 25Gbps each) at `10.10.68.107/23`.

## How to Run

Invoke through the `terminal` tool via the jump host:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=10 jianliu@10.10.68.107 'command'"
```

## Quick Reference

| Item | Value |
|------|-------|
| Hostname | `oemp107` |
| OS | Ubuntu 22.04.5 LTS (kernel 5.15.0-119-generic) |
| GPU | 8× NVIDIA RTX 6000D (Blackwell GB202, CC 12.0 / sm_120), PCI `10de:2bb9`, each 85,651 MiB VRAM |
| Driver | **INSTALLED**: NVIDIA 610.43.02, CUDA UMD 13.3, `/dev/nvidia0-7` present |
| RAM | 1 TiB (128 CPU threads, 2× Xeon Gold 6530, 32c/socket) |
| Root disk | 98G (LVM), 78G free |
| NVMe | 2× 3.5T → LVM VG `vg0-datalv` **mounted at `/home`** (7.0T, ~6.6T free) |
| Storage | `/modelzoo` = NFS `10.10.68.71:/data` (14T, ~8.6T free) — world-writable |
| RDMA | Mellanox ConnectX-7 (MT4129, `mlx5_0`, port → `ens35np0`, fw 28.43.8016) — **verified 400Gb/s Ethernet link** (ibstat Rate: 400, 2026-09-11); + 2× ConnectX-4 Lx 25GbE (mlx5_bond_0 → bond0); OFED + knem + kernel-mft-dkms installed |
| Net mgmt | `10.10.68.107/24`, gw `10.10.69.254` |
| Net cluster | `10.10.68.107/23` on bond0 (802.3ad LACP 2×25G) |
| Docker | **INSTALLED** (Server 29.7.2 / API 1.55), root dir `/home/docker` (on vg0-datalv), overlay2. `jianliu` in `docker` group — **no sudo needed** for docker. **nvidia-container-toolkit 1.20.0 installed** — `--gpus all` works |
| nvidia-smi | **WORKS** (driver installed) — use `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` |
| Sudo | `liujian` **HAS sudo since 2026-09-04** (added to sudo group via `qs`; verified `sudo whoami` = root, password `985202Qs~`). `qs` (local uid 1000, sudo+docker) still logs in with OLD password `!QAZ2wsx` |
| Users | `jianliu` **DELETED** (verified 2026-09-04: `id: no such user`, /home/jianliu gone — that's why password auth "broke" 0903); NEW login `liujian` (domain account, password-auth only); `qs` (uid 1002) |

## Procedure

### 1. Basic connectivity and GPU check

nvidia-smi works now (driver installed). Confirm GPU fleet:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 \
    'hostname && nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader'"
```

Expected output (8× RTX 6000D, 85,651 MiB each):
```
oemp107
0, NVIDIA RTX 6000D, 85651 MiB
... (8 entries)
```

GPU model: `10de:2bb9` = **GB202GL [RTX 6000D]** (confirmed via devicehunt.com). Blackwell CC 12.0 / sm_120.

### 2. System resources

```bash
# Disk (note /modelzoo NFS mount)
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 'df -h'"

# Memory
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 'free -h'"

# LVM (NVMe VG)
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 \
    'echo !QAZ2wsx | sudo -S vgs'"
```

### 3. /modelzoo shared storage

NFS mount from `10.10.68.71:/data` (14T). Contains cluster models:
`Kimi-K3`, `MiniMaxAI`, `Qwen3-8B`, `Qwen3.5-9B`, `Qwen3.6-35B-A3B-FP8/NVFP4`, `deepseekv4-flash-0731`, `deepseekv4_flash`, `deepseekv4_pro`, `deepseekv4_pro_0813`, `glm_5_2_nvfp4`, `minimax_m2_7_nvfp4`, `wan2.2_t2v_A14B`, `qwen_image_2512`, `stable-diffusion-2-base`.

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 'ls /modelzoo/'"
```

### 4. Sudo access

Same password as login (`!QAZ2wsx`). Use `sudo -S` for non-interactive:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 \
    'echo !QAZ2wsx | sudo -S apt-get update'"
```

### 5. Docker (INSTALLED — jianliu in docker group)

Docker Server 29.7.2 / API 1.55, root dir `/home/docker` (on `vg0-datalv`, 7TB), overlay2. `jianliu` is in the `docker` group — no sudo needed for docker commands:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 \
    'bash --noprofile --norc -c \"docker images\"'"
```

**CRITICAL — conda pollutes the pipe:** The login shell on 107 runs a broken conda init that crashes and dumps a huge "An unexpected error has occurred" report to stdout/stderr on EVERY SSH command. This corrupts any `docker save | ssh ... | docker load` pipe. **Always use `bash --noprofile --norc -c '...'`** for the remote command when piping data, or the tar stream gets garbage and `docker load` fails with `invalid archive: does not contain a manifest.json`.

Copy an image from 68.96 to 107 (reliable method — save to tar on 96, then stream to docker load):

```bash
# Step 1: save on 96 (writes /tmp/.tmp-* then renames; 68GB image → ~32G tar)
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "docker save IMAGE:TAG -o /tmp/img.tar"

# Step 2: stream tar to 107 and load (over bond0 10.10.68.107, ~25Gbps)
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "cat /tmp/img.tar | sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.107 \
    'bash --noprofile --norc -c \"docker load\"'"
```

**Status 2026-08-25:** `fathomless-main-verify:gpu-smoke-fix6` successfully copied from 68.96 → 68.107 (loaded, 33.8GB, ID `2ebaedeee209`). NOTE: image ID differs from source (`7c0813e0b7bd`) after save/load round-trip.

**GPU-in-container: WORKING (2026-08-25)** — nvidia-container-toolkit **1.20.0** installed and configured. `docker run --rm --gpus all fathomless-main-verify:gpu-smoke-fix6 nvidia-smi -L` sees all 8× RTX 6000D; PyTorch 2.12.0+cu132 in-container reports `cuda.is_available()=True`, `device_count()=8`; 4096×4096 CUDA matmul verified on `cuda:0 NVIDIA RTX 6000D`.

**Installation recap (nvidia-container-toolkit on Ubuntu 22.04, amd64):**
1. Get `gpgkey` + `nvidia-container-toolkit.list` from `https://nvidia.github.io/libnvidia-container/...` (flaky — retry; `.list` uses `$(ARCH)` → replace with `amd64`, add `[signed-by=...]`).
2. Cache sudo first: `printf '%s\n' "$PW" | sudo -S -v` — **NEVER** pipe password into `sudo -S cmd < file` (stdin conflict corrupts both password and data). Do NOT use `echo !QAZ2wsx` (bash history expansion breaks the `!`); base64-encode the password in scripts.
3. `sudo apt-get install -y nvidia-container-toolkit` (installs nvidia-ctk, nvidia-container-runtime, nvidia-container-cli).
4. `sudo nvidia-ctk runtime configure --runtime=docker --config /etc/docker/daemon.json && sudo systemctl restart docker`.
5. Verify: `docker run --rm --gpus all IMAGE nvidia-smi -L`.

## GitLab 10.10.50.23 (company model-deployment repo)

Independent GitLab instance reachable from 107 (and other cluster nodes). **SSH auth works** — 107's `/home/jianliu/.ssh/id_rsa` is registered as GitLab user **`@liujian`** (note: liujian, not jianliu). The jump host 96's SSH keys are also authorized (same `@liujian`) — this GitLab is usable from any cluster node whose key is registered.

- Web: `http://10.10.50.23` (nginx, 302 → `/users/sign_in` = GitLab; `/api/v4/version` → 401 unauth)
- **HTTP clone needs credentials** (302 to login) — use SSH instead:
  ```bash
  git clone git@10.10.50.23:tgu01-pro/tgu01-pro-model-deployment.git
  ```
- Repo `tgu01-pro/tgu01-pro-model-deployment` cloned on 107 at `/home/jianliu/work/tgu01-pro-model-deployment` (main, 795 files). Branches: `main`, `liuchao/glm-nvfp4-sparse-benchmarks`, `tmp_zjl`. Top dirs: deepseekv4_flash/pro, glm5_2_nvfp4, glm5_nvfp4, kimi3, minimax_h3/m2_7/m3_nvfp4, mooncake_kv_offload, nccl, qwen3_235b, qwen_3_6, qwen_image_2512, sd2, vllm_bench_standard_test, wan_2_2_fp16, scripts.
- Other repos likely under same group (`tgu01-pro/`). SSH key auth means no password prompt.

## Pitfalls

- **Conda crash pollutes every SSH command** — The login shell on 107 runs broken conda init that dumps a giant error report. Always wrap remote data-piping commands in `bash --noprofile --norc -c '...'`. Never `sudo -S docker load` in a pipe (password prompt corrupts the stream).
- **`!` in password** — Always single-quote `'!QAZ2wsx'` in `sshpass -p` and when piping to `sudo -S`. Never double quotes (bash history expansion).
- **`/data/` not present** — Storage is the NFS `/modelzoo` (10.10.68.71). No local `/data/` structure.
- **Two NICs, two subnets** — mgmt `10.10.68.107`, cluster `10.10.68.107`. NFS/RDMA traffic goes over bond0 (10.10.68.x). Default route via 10.10.69.254.
- **NVMe is LVM `vg0-datalv` mounted at `/home`** (7TB) — docker root lives there. Don't touch the LVM without intent.
- **RTX 6000D is Blackwell GB202** (CC 12.0 / sm_120), NOT Ada (like 103). Driver/NCCL/Triton requirements differ (sm_120 support needed).
- **Users**: `jianliu` (uid 1001, in sudo+docker groups), `qs` (uid 1002), + uid 1003/1004 (model owners). `/modelzoo` is world-writable (drwxrwxrwx).
- **driver stack** NVIDIA 610.43.02 + CUDA UMD 13.3; `/dev/nvidia0-7` present. nvidia-smi works normally.

## PD Disaggregation (2026-09-01)

`/userdata/jianliu/work/tgu01-pro-model-deployment/pd_disaggregation/` — Notion test design "PD" (page 3cd4b7bb34d8801487fbe66df9788567): DeepSeek V4 Flash, Prefill TP=4 (GPU 0-3, kv_producer) + Decode TP=4 (GPU 4-7, kv_consumer) + proxy, MooncakeConnector KV transfer. Scripts:
- `start_pd_disaggregation.sh` — launches decode → prefill → proxy containers (image `fathomless-main-verify:gpu-smoke-fix6`, serving flags mirror `../deepseekv4_flash/start_dsv4_flash_1node_fathomless_main_docker.sh`; TP=4 per half, per-role cache dirs, `--kv-transfer-config MooncakeConnector`, tcp protocol, bootstrap port 8998).
- `stop_pd_disaggregation.sh` — removes containers + leftover proxy.
- `run_pd_test_flow.sh` — full 6-point matrix (2K/512 C8+C64, 16K/512 C64 × baseline/PD, 3 runs median; `--check` preflight, `--execute` run). Baseline = `start_dsv4_flash_pro6_best.sh` TP=8.

Key facts:
- fathomless image HAS MooncakeConnector code (`vllm/distributed/kv_transfer/kv_connector/v1/mooncake/`) but NOT the `mooncake` python package → bind-mount pre-extracted x86-64 runtime `/userdata/jianliu/work/agentx_mooncake_v2/shared_cache/mooncake-runtime/300224d265038befc4f1dcbcdee02bf850bf5ac9bfc649b542d188d1265ef0ec` (mooncake 0.3.10.post2 from `vllm/vllm-openai:v0.25.0-flashinfer0614-local`) to `/opt/mooncake-runtime` and prepend to PYTHONPATH.
- Mooncake runtime extraction pattern from `deepseekv4_flash/start_dsv4_flash_pro6_fix6_mooncake_kv_offload.sh` (`prepare_mooncake_runtime()`).
- Proxy: `examples/disaggregated/mooncake_connector/mooncake_connector_proxy.py` (in-image), args `--prefill URL --decode URL --port N`; send test traffic to proxy port 8000 only.
- Model on 107: `/modelzoo/deepseekv4-flash-0731` (156G, 48 shards). `/data/models` does NOT exist on 107 (that's the 96/98 path); `/userdata` is NFS.
- Port 8001 = qs's dspark server (xiaqing) — do not kill. PD stack uses 8100/8200/8000+8998.
- `vllm bench serve` runs inside the serving image (no host venv); use `--backend openai-chat` for chat-format loads.

## Verification

Confirm reachability:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=10 jianliu@10.10.68.107 'hostname'"
```

Expected output: `oemp107`
