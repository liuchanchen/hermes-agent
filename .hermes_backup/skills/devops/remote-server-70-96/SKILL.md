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

From WSL — plain SSH with key auth, NO password needed (verified 2026-09-04):

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 '<command>'
```

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
| Idle monitor | cron job `a3007169683e` (fires when GPUs free up) |

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
