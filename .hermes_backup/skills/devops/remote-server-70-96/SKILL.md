---
name: remote-server-70-96
description: Use when accessing GPU server 10.10.68.96.
version: 0.1.0
author: Hermes Agent
platforms: [linux]
metadata:
  hermes:
    tags: [GPU, RTX-PRO-6000, Blackwell, Remote, Server, WarpDrive, RDMA]
---

# Remote Server 10.10.68.96

8× NVIDIA RTX PRO 6000 Blackwell SE (96 GB, 97887 MiB each, sm_120), driver 595.71.05 — **nvidia-smi WORKS** (no stub, unlike TGU01-Pro nodes). One of the busiest cluster nodes: PD disaggregation host, GLM experiments, and the jump host toward 106/107.

## When to Use

- "Log in to 96" / check GPUs / disk on 96
- PD disaggregation runs (see the `pd-disaggregation` skill for the recipe)
- Jump host toward 107 (password auth dead since 2026-09-03 — route currently unavailable) or 106

## How to Run

From WSL — `ssh oem96` (Host alias = domain `liujian` + `~/.ssh/id_ed25519_vscode`, BatchMode works, re-verified 2026-11-13):

```bash
ssh -o StrictHostKeyChecking=no oem96 '<command>'
```

**Two management IPs, only one accepts SSH (2026-11-09):** `10.10.70.96` and
`10.10.68.96` both answer ping and present the **same host key**, but
`10.10.70.96` resets every handshake at kex (`kex_exchange_identification: read:
Connection reset by peer`). Use `10.10.68.96` / `oem96`; a cron probe aimed at
`10.10.70.96` looks like "node down" while the node is perfectly fine.

**Local `jianliu@` key auth is dead (2026-11-09):** `ssh jianliu@10.10.68.96` returns `Permission denied (publickey,password)`. Use the alias/domain account; `liujian` has no docker group and no sudo (use `jianliu`/`!QAZ2wsx` when root is needed).

**Domain account (2026-09-23, verified):** 96 is domain-joined — login `liujian` / `985202Qs~` (same as 106/107, uid 178201608) also works. **Domain liujian has NO sudo** (`not in the sudoers file`); the old local `jianliu`/`!QAZ2wsx` (uid 1001) still authenticates and retains sudo+docker. `/home/jianliu` (old work tree) is now owned by the domain-liujian uid. From WSL without sshpass/pexpect use the SSH_ASKPASS pattern (see umbrella skill).

From 96 to 106 (sshpass is installed on 96):

```bash
sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.106 '<command>'
```

## Quick Reference

| Item | Value |
|------|-------|
| GPU | 8× RTX PRO 6000 Blackwell SE, 96 GB (97887 MiB) each, sm_120 |
| Driver | 595.71.05; `nvidia-smi` works |
| Sudo | **works for jianliu** — in sudo(27)+docker(138) groups; no passwordless sudo, use `sudo -S -v` with `!QAZ2wsx` (verified 2026-09-04; earlier "rejected" note was wrong) |
| Docker | works without sudo |
| Net mgmt | 10.10.68.96 |
| Net cluster | bond0 = 10.10.68.96/23 |
| **RDMA** | **`mlx5_1`** (netdev ens35f1np1, bond0 slave) RoCE 100G ACTIVE, MTU 9000; `mlx5_0` InfiniBand DOWN. mooncake device_name = **mlx5_1** — NOT `mlx5_bond_0` (that's 106's name; scripts ported from 106 with the hardcoded 106 name fail) |
| /dev/infiniband | uverbs0, uverbs1, rdma_cm, umad present |
| GPUDirect peermem | `nvidia_peermem` loaded via `sudo modprobe` 2026-09-04 + persisted in `/etc/modules-load.d/nvidia-peermem.conf` (module .ko from DKMS: `/lib/modules/6.8.0-111-generic/updates/dkms/`; 8 GPUs `Peer Type: Direct Connected`) |
| NFS | `/userdata` = 10.10.68.71:/data **WRITABLE** (deployment dir + results live here); `/modelzoo` read-only models |
| mooncake runtimes | `~/mooncake-runtime-0.3.11` (pypi wheel, bundles `.libs`) and `~/mooncake-runtime-0.3.10` (106's tar + hashed libs copied from 0.3.11 with `cp -L`) |
| Other users | xuechenli, yirongpan (sudo+docker) — never kill foreign workloads |
| Idle monitor | cron job `a3007169683e` — probe `~/.hermes/scripts/monitor_70_96_idle.sh` (oem96, key auth); agent fires only when probe output changes |

## Workload History

- **PD disaggregation**: smoke PASSED + full baseline/PD matrix 2026-09-04 — see the `pd-disaggregation` skill and its `references/70-96-experiment-2026-09-04.md`. Deployment dir: `/userdata/jianliu/work/tgu01-pro-model-deployment/pd_disaggregation/` (NFS).
- **GLM-5.2-NVFP4**: custom_all_reduce crashes on SM12.0 (Blackwell) — known limitation.
- GLM-5.3 prefill experiments land here too (check `docker ps` + GPU memory before scheduling).

## Pitfalls

- **MOONCAKE_DEVICE differs per host**: 96 uses `mlx5_1`; 106 uses `mlx5_bond_0`.
- Non-interactive SSH worked without `source ~/.bashrc` in the 2026-09-04 session; if a command misses proxy vars, prefix `source ~/.bashrc &&`.
- sudo has no NOPASSWD (needs `!QAZ2wsx` via `sudo -S -v`); staging runtimes under `~/` is still preferred when possible (see the pd-disaggregation skill for the hashed-libs trap).
- 106 is reachable both directly from WSL AND via 96; prefer direct unless 96 is the anchor (NFS results, sshpass to other nodes).

## Verification

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 'nvidia-smi --query-gpu=index,memory.used --format=csv,noheader'
# Expected: 8 rows, ~14 MiB when idle
# (hostname string not captured — fill in on first login)
```

**Idle判定 (2026-11-13)**: 只看显存不够 — 同时查 `nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l` 必须为 0，并 `docker ps` 确认无容器。**注意**: 以 domain `liujian` 登录时 `docker ps` 报 `permission denied ... docker.sock`（不在 docker 组），此时以 compute-apps=0 + 8×14 MiB/0% 为准即可（无 compute 进程即无 GPU 容器负载）；需要容器清单时用 `jianliu`/`!QAZ2wsx` — 本机无 sshpass，用 SSH_ASKPASS 脚本 + `setsid -w ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no jianliu@10.10.68.96 'docker ps ...'`（2026-11-13 验证可用，空输出=无容器）。二次采样间隔 10s 显存不变可排除加载中。**探针快照会早于启动数秒 (2026-11-13)**: cron 探针报 8×17 MiB 的同时, 容器内 vLLM DP3/EP3 worker (root, docker 60dc4a33…, `VLLM::Worker_DP3_EP3`) 已开始加载, 10s 后 8 卡齐涨到 53 GiB —— 绝不能凭单次探针行判空闲, 必须重跑 compute-apps + 10s 二次采样。`who` 里有 xiaqing / wanglei 等登录用户不代表在用卡；qs 常驻一个 CPU-only `python server.py --host 0.0.0.0 --port 8199`（0.2% CPU，无显存），不构成 GPU 占用。
