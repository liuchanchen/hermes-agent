---
name: server-discovery-update
description: Discover new servers and update the umbrella skill.
version: 0.1.0
author: Hermes
metadata:
  hermes:
    tags: [Server, Discovery, SSH, Inventory, GPU]
---

# Server Discovery & Skill Update

Procedure for discovering a new GPU server from credentials provided by the user and immediately updating the `devops/remote-server-management` umbrella skill with the findings. Covers hands-on probing via SSH/pexpect, cross-referencing hardware/software against known nodes, authoring a reference document, and patching all relevant tables (Supported Servers, Model Inventory, Known Server Configs) in the umbrella skill.

Does NOT cover OS provisioning, RAID/LVM setup, or NVIDIA driver installation — only discovery and documentation of the as-delivered state.

## When to Use

- User provides IP + username + password for a new server
- User says "check this server" or "add this node"
- Exploring a server whose specs are unknown during a live session
- Adding a server IP that appeared in memory or config but wasn't documented in the skill

## Prerequisites

- Access to the remote-server-management skill directory:
  `~/.hermes/skills/devops/remote-server-management/`
- Python `pexpect` available (Hermes env usually has it)
- Network reachability to the target server (`ping` check first)

## How to Run

The canonical workflow is:

1. Verify reachability via `terminal` (`ping -c 2 -W 3 <IP>`)
2. Probe with `pexpect-ssh.py` using provided credentials
3. Cross-reference PCI IDs (`1ec8:8900` / `1ec8:8904` = TGU01-Pro; `10de:2b85` = RTX 5090; `10de:2bb5`/`10de:2bb9` = RTX PRO 6000 Blackwell SE)
4. Compare against the Supported Servers table to spot unique characteristics
5. Author a reference doc in `references/`
6. Patch the umbrella skill tables (Supported Servers, Model Inventory, Known Server Configs, No-proxy list)
7. Update the skill version and model inventory date

## Quick Reference

```bash
# Reachability check
ping -c 2 -W 3 10.10.68.XX

# Full probe command via pexpect-ssh.py
cd ~/.hermes/skills/devops/remote-server-management && \
  python3 scripts/pexpect-ssh.py 10.10.68.XX user 'password' \
  'hostname && hostnamectl && lspci -nn | grep -iE "nvidia|1ec8|vga|3d" && \
   nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader && \
   uname -r && grep "model name" /proc/cpuinfo | head -1 && free -h | head -2 && \
   df -h / /data 2>/dev/null && cat /etc/os-release | head -3 && \
   docker --version && docker ps -a 2>/dev/null | head -5 && \
   getent passwd | grep -E "home/|/bin/bash" | cut -d: -f1,6,7 && \
   lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT && \
   ip addr show | grep -E "^[0-9]|inet " | grep -v "127.0.0.1|::1"' 30

# GPU PCI ID reference
#  1ec8:8900 / 1ec8:8904 = WarpDrive TGU01-Pro (no NVIDIA driver)
#  10de:2b85           = RTX 5090
#  10de:2bb5 / 2bb9    = RTX PRO 6000 Blackwell SE
#  10de:2684           = RTX PRO 6000 (Ada)
#  10de:2688           = RTX 5090D
```

## Procedure

### 1. Reachability and Auth Check

```bash
# Quick ping
ping -c 2 -W 3 10.10.68.XX

# Try SSH key auth first (if known host)
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 jianliu@10.10.68.XX "hostname"

# Fallback to pexpert for password auth
cd ~/.hermes/skills/devops/remote-server-management
python3 scripts/pexpect-ssh.py 10.10.68.XX jianliu '!QAZ2wsx' 'hostname' 20
```

If the default password fails, try alternate username `qs` — some WarpDrive nodes have jianliu with a different password.

### 2. Comprehensive Probe

Run a single probe command that covers:
- **Host identity**: hostname, hostnamectl (vendor, model, chassis)
- **GPU**: lspci -nn for NVIDIA/WarpDrive devices, nvidia-smi for model/driver/VRAM
- **CPU**: model name, core count from /proc/cpuinfo
- **Memory**: `free -h`
- **Disk**: `df -h / /data`, `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT`
- **OS/Kernel**: `/etc/os-release`, `uname -r`
- **Docker**: version, running containers, images
- **Users**: `getent passwd` for home/bash users
- **Networking**: `ip addr show` interfaces, look for RDMA (ens35f0np0, bond0)
- **SSH keys**: `ls -la ~/.ssh/`
- **NCCL**: `dpkg -l libnccl2`
- **NVIDIA driver**: `cat /proc/driver/nvidia/version` for kernel module version

### 3. Identify Server Type

Cross-reference PCI IDs and CPU:

| Pattern | Type | Characteristics |
|---------|------|----------------|
| `1ec8:8900/8904` | **WarpDrive TGU01-Pro** | No nvidia-smi, use wd-smi, openEuler or Ubuntu, stub exit 113 |
| `10de:2bb5` | **RTX PRO 6000 Blackwell SE** | 8 GPUs, 3D controller class 0302, NCCL ≥ 2.30 required |
| `10de:2b85` | **RTX 5090** | 8 GPUs, VGA class 0300, Kernel 6.8.x |
| Only 2 GPUs `10de:2bb9` | **RTX PRO 6000 Blackwell SE (2×)** | Partial-population node, smaller form factor |
| Xeon Platinum 8558P | 48c, 260MB L3 — **best alltoall** |
| Xeon Gold 6530 | 32c, 160MB L3 — standard |

### 4. Cross-Reference Against Skill

Read the `Supported Servers` table from the umbrella skill and compare notes. Look for:
- Whether this IP already has an entry (stale or current)
- Whether GPU model matches known types
- Whether there's a proxy (check `.bashrc` for `export http_proxy`)
- Whether `/data/` exists and its mount source
- Whether RDMA interfaces (ens35f0np0, bond0) are up
- Unique quirks: NVML mismatch, broken jianliu password, missing SSH keys, LVM layout

### 5. Author Reference Document

Create a markdown file at `references/70-XX-initial-setup.md` via `skill_manage` write_file with:

- Hardware table (vendor, model, GPU, CPU, RAM, Disk, NIC)
- Software table (OS, kernel, driver, NCCL, Docker)
- Key Differences from other nodes (table)
- GPU Discovery section (lspci output)
- Any driver/library mismatches
- Docker registry info and available images
- Available models
- User list
- Current status (running services, issues)
- Quick Reference commands
- Initial setup checklist (if bare node)

### 6. Patch the Umbrella Skill

Via `skill_manage(action='patch', name='remote-server-management')`:

- **Supported Servers table**: Add full row with all key details. Use bold for standout characteristics.
- **Model Inventory**: Add 70.XX column header. Fill model paths from probe. Add `—` for absent models.
- **Known Server Configs**: Add row with port, API key, startup script, setup notes.
- **No-proxy servers list**: If no proxy, add XX to the line like `(66, 93, 98, 99, XX)`.
- **Model inventory date**: Update to today's date.
- **Version**: Bump minor version (1.x.0 → 1.x+1.0).

### 7. Update Change Log

Patch `references/skill-update-log-2026-07-18.md` with a structured entry describing each change.

## Pitfalls

- **Password may not match for jianliu** — Some nodes (e.g., 68.90) have jianliu with a different password while qs/!QAZ2wsx works. Always try both.
- **nvidia-smi stub**: On TGU01-Pro nodes, `/usr/local/bin/nvidia-smi` is a shell script that `exit 113`. Check with `which nvidia-smi && file $(which nvidia-smi)`.
- **NVML mismatch**: If `nvidia-smi` says "Failed to initialize NVML: Driver/library version mismatch", compare `cat /proc/driver/nvidia/version` (kernel module) vs `strings /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.595* | grep NVML_VERSION` (library). Reboot is the fix.
- **SSH hostname shorthand**: Always use full IP `10.10.68.XX` — short names like `68.90` may resolve to wrong IPs.
- **Proxy servers**: 68.88/95/96 need `source ~/.bashrc &&` before commands in non-interactive SSH.
- **Single-file probe commands in pexpect**: Keep the command short enough to avoid timeout. Use multiple invocations if needed.
- **Data partition paths differ**: `/data/` vs `/data/home/` vs `/home/` — the base path for models varies by server. Always check.
- **Model paths may be on /data/home/ not /data/**: 68.90 has models at `/data/home/public/models/`, not `/data/models/`.

## Verification

```bash
# Re-read the patched skill table entry to confirm it's correct
grep -A 1 "10.10.68.XX" ~/.hermes/skills/devops/remote-server-management/SKILL.md | head -3
```
