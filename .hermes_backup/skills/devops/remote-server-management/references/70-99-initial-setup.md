# 10.10.70.99 (oem-99) — WarpDrive TGU01-Pro Initial Setup

## Hardware

| Attribute | Value |
|-----------|-------|
| Vendor | WARPDRIVE |
| Model | Bumblebee BI5284 |
| GPU | WarpDrive TGU01-Pro 32GB × **8** (PCI ID `1ec8:8900` + `1ec8:8904` — same as 70.93) |
| CPU | Intel Xeon Gold 6530 (32c/socket, 160MB L3, 128 threads, 2 NUMA) |
| RAM | 1.0 TiB |
| System Disk | 1.7 TB (sda2, ext4, `/`) |
| Data Disk | 3.5 TB LVM (nvme0n1 → `datavg-datalv` → ext4 → `/home`) |
| Mgmt NIC | ens20f0 — 10.10.70.99/24, gateway 10.10.70.254 |

## Software

| Component | Version |
|-----------|---------|
| OS | Ubuntu 22.04.4 LTS (Jammy) |
| Kernel | **5.15.0-185-generic** (older than other TGU nodes on 6.8.x) |
| Docker | 27.2.1 (installed, but jianliu NOT in docker group) |
| NVIDIA Driver | **NOT INSTALLED** — no nvidia-smi, no nvidia-utils |
| wd-smi | Present (WarpDrive's GPU monitoring, no nvidia-smi fallback) |
| SSH Keys | **None** — `~/.ssh/` does not exist, password auth only |

## Key Differences from Other TGU Nodes

| Aspect | 70.93/70.92/70.94 | 70.99 |
|--------|-------------------|-------|
| Kernel | 6.8.x | **5.15.0-185** (older) |
| NVIDIA Driver | 580.x or 595.x | **None** |
| `nvidia-smi` | Stub (exit 113) or real | **Not installed at all** |
| `/data/` partition | Present (LVM) | **No `/data/`** — 3.5TB goes to `/home` |
| SSH Keys | Configured | **Not configured** |
| Docker group | jianliu has access | **Not in docker group** |
| Proxy | Some servers | **No proxy** |

## GPU Discovery

8 TGU01-Pro devices found via `lspci -nn`:

```
16:00.0 3D controller [0302]: Device [1ec8:8900]
16:00.2 3D controller [0302]: Device [1ec8:8904]
27:00.0 3D controller [0302]: Device [1ec8:8900]
27:00.2 3D controller [0302]: Device [1ec8:8904]
38:00.0 3D controller [0302]: Device [1ec8:8900]
38:00.2 3D controller [0302]: Device [1ec8:8904]
5a:00.0 3D controller [0302]: Device [1ec8:8900]
5a:00.2 3D controller [0302]: Device [1ec8:8904]
98:00.0 3D controller [0302]: Device [1ec8:8900]
98:00.2 3D controller [0302]: Device [1ec8:8904]
a8:00.0 3D controller [0302]: Device [1ec8:8900]
a8:00.2 3D controller [0302]: Device [1ec8:8904]
b8:00.0 3D controller [0302]: Device [1ec8:8900]
b8:00.2 3D controller [0302]: Device [1ec8:8904]
d8:00.0 3D controller [0302]: Device [1ec8:8900]
d8:00.2 3D controller [0302]: Device [1ec8:8904]
```

Same `1ec8:8900` + `1ec8:8904` pairing pattern as 70.93 — each physical GPU has two PCIe functions (compute + media/display?).

## Networking

| Interface | Link | IP | Notes |
|-----------|------|----|-------|
| ens20f0 | UP | 10.10.70.99/24 | Management — same subnet as other 10.10.70.x nodes |
| ens20f1 | DOWN | — | Secondary management (LAG capable?) |
| ens20f2 | DOWN | — | |
| ens20f3 | DOWN | — | |
| ens35f0np0 | DOWN | — | Likely ConnectX-6 Dx 100GbE (same as 70.96/70.98) |
| ens35f1np1 | DOWN | — | Second port |
| docker0 | UP | 172.17.0.1/16 | Default Docker bridge |

**RDMA not configured** — all high-speed interfaces are DOWN. No bond0, no RoCE v2. ens35f0np0 needs driver setup and cable.

## /etc/hosts

```
127.0.0.1 localhost
127.0.1.1 oem-99
```

Has the standard Ubuntu `127.0.1.1` mapping — will cause Gloo/SSH issues in multi-node DP just like 70.98's initial state. Must fix before multi-node vLLM use.

## User Setup

| User | UID | Groups | Home | Shell |
|------|-----|--------|------|-------|
| qs | 1000 | qs | /home/qs | /bin/bash |
| jianliu | 1001 | jianliu, sudo | /home/jianliu | /bin/bash |

jianliu has sudo access but no SSH keys. Password auth works with `!QAZ2wsx`.

## Quick Reference Commands

```bash
# Connect (password auth only)
ssh -o StrictHostKeyChecking=accept-new jianliu@10.10.70.99

# From Hermes (pexpect fallback)
cd ~/.hermes/skills/devops/remote-server-management && \
  python3 scripts/pexpect-ssh.py 10.10.70.99 jianliu '!QAZ2wsx' 'hostname' 20

# Check GPU status
python3 scripts/pexpect-ssh.py 10.10.70.99 jianliu '!QAZ2wsx' 'wd-smi' 20

# Check disk
python3 scripts/pexpect-ssh.py 10.10.70.99 jianliu '!QAZ2wsx' 'df -h' 20

# Bootstrap SSH keys (run from a jump host with key auth)
PUBKEY=$(cat ~/.ssh/id_ed25519.pub)
sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.70.99 \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$PUBKEY' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

## Initial Setup Checklist

- [ ] **Bootstrap SSH keys** (from 70.96 or another jump host with key auth)
- [ ] **Add jianliu to docker group**: `sudo usermod -aG docker jianliu`
- [ ] **Install NVIDIA driver** (nvidia-utils-595 or 580 — depends on driver compat)
- [ ] **Fix /etc/hosts** — remove `127.0.1.1 oem-99` and add `10.10.70.99 oem-99`
- [ ] **Create /data/ partition** — needs LVM reconfiguration or new disk
- [ ] **Install CUDA toolkit + NCCL** if planning GPU compute
- [ ] **Configure RDMA** — setup bond0 + RoCE v2 on ens35f0np0/f1np1
- [ ] **Auto-detect NCCL_IB_HCA**: `rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,'`
- [ ] **Copy nccl-tests** from another node and rebuild against local NCCL
