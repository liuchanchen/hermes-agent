---
name: remote-server-70-103
description: Access and manage 2x RTX 6000D server.
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [GPU, RTX6000D, Remote, Server, WarpDrive]
---

# Remote Server 10.10.68.103

Access and management for the Bumblebee BI5284 server at `10.10.68.103` with **2× NVIDIA RTX 6000D** GPUs (Ada Lovelace, compute capability 8.9). The server runs Ubuntu 22.04.4 LTS with driver 595.71.05. It is directly reachable from jump host `10.10.68.96` on the same subnet with low latency (~0.3ms ping).

**What this does NOT cover:** Model deployment, NCCL benchmarks, or cluster orchestration. For those, see `devops/remote-server-management`.

## When to Use

- "Log in to 10.10.68.103"
- "Check what GPU the Bumblebee server has"
- "What models are on 103?"
- "Check disk/memory on 103"

## Prerequisites

- **Jump host**: `10.10.68.96` (key auth or password `!QAZ2wsx`). The jump host has `sshpass` 1.09 pre-installed.
- **Credentials**: `jianliu` / password `!QAZ2wsx`. Same password for `sudo` access. Password-auth only (SSH keys not configured unless explicitly set up).
- **Network**: Reachable directly on `ens20f0` (1 GbE) from 68.96. No proxy needed — direct internet access.

## How to Run

Invoke through the `terminal` tool via the jump host:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=10 jianliu@10.10.68.103 'command'"
```

## Quick Reference

| Item | Value |
|------|-------|
| Hostname | `warpdrive-Bumblebee-BI5284` |
| OS | Ubuntu 22.04.4 LTS (kernel 6.x) |
| GPU | 2× NVIDIA RTX 6000D (Ada Lovelace, CC 8.9) |
| Driver | 595.71.05 |
| RAM | 125 GiB |
| Root disk | 879G, 703G free (16% used) |
| `/data/` | Exists but jianliu has no read permission |
| `/data/models/` | Does not exist |
| `/home/public/models/` | Contains `tgu01/` directory |
| Proxy | None (direct internet) |
| nvidia-smi | Standard — no stub/wrapper issue |
| Sudo | Same password: `!QAZ2wsx` |

## Procedure

### 1. Basic connectivity and GPU check

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=10 jianliu@10.10.68.103 \
    'hostname && nvidia-smi --query-gpu=name,driver_version --format=csv,noheader'"
```

Expected output:
```
warpdrive-Bumblebee-BI5284
NVIDIA RTX 6000D, 595.71.05
NVIDIA RTX 6000D, 595.71.05
```

### 2. System resources

```bash
# Disk
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.103 'df -h /'"

# Memory
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.103 'free -h'"
```

### 3. Sudo access

The sudo password is the same as the login password (`!QAZ2wsx`). Use `sudo -S` for non-interactive sudo:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.103 \
    'echo !QAZ2wsx | sudo -S apt-get update'"
```

**Important:** The `!` character triggers bash history expansion in interactive shells. Use single quotes for the password string (as shown above) to prevent this. In `sshpass -p '!QAZ2wsx'`, the single quotes protect the exclamation mark.

### 4. Install a package

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no jianliu@10.10.68.103 \
    'echo !QAZ2wsx | sudo -S apt-get install -y PACKAGE'"
```

## Pitfalls

- **`!` (exclamation mark) in password** — `!QAZ2wsx` contains `!` which triggers bash history expansion. Always wrap the password in **single quotes** (`'!QAZ2wsx'`) in `sshpass -p`. Never use double quotes. When echoing to `sudo -S`, use single quotes around the echo argument: `echo '!QAZ2wsx' | sudo -S command`.
- **`/data/` is not accessible** — jianliu gets `Permission denied` reading `/data/`. If you need to access `/data/`, use `sudo` (e.g., `echo '!QAZ2wsx' | sudo -S ls /data/`).
- **No `/data/models/` directory** — Unlike the 10.10.68.x cluster servers, this server does not have a `/data/models/` structure. Model storage is at `/home/public/models/tgu01/` if anything.
- **RTX 6000D is Ada Lovelace** (compute capability 8.9), **not Blackwell** (sm_120). NCCL version requirements differ — older NCCL versions work fine.
- **2 GPUs only** — Not suitable for 8-GPU TP setups. Suitable for small model inference, testing, or as a development node.
- **No proxy** — Direct internet access, unlike servers 68.88/68.95/68.96 which have proxy in `.bashrc`.
- **nvidia-smi works normally** — No stub/wrapper issue unlike some WarpDrive servers.

## Verification

Confirm the server is accessible and GPU is recognized:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '!QAZ2wsx' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=10 jianliu@10.10.68.103 \
    'hostname'"
```

Expected output: `warpdrive-Bumblebee-BI5284`
