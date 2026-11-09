---
name: update-node-12-12-password
description: Change SSH password on internal H100 node.
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [SSH, Credentials, H100, Password, Server]
---

# Update 192.168.12.12 SSH Password

Procedure to change the SSH login password for `jianliu` on the internal H100 GPU node at `192.168.12.12`. The node runs Ubuntu 22.04.3 LTS, requires password-based SSH authentication (no SSH keys configured), and is a standalone server with 8× NVIDIA H100 80GB GPUs serving DeepSeek-V4-Flash via vLLM.

**What this does NOT cover:** Changing passwords on 10.10.70.x cluster nodes, SSH key setup, or user creation.

## When to Use

- "Update 12.12's password"
- "Change the SSH password on the H100 node"
- "Reset jianliu's login on 192.168.12.12"

## Prerequisites

- **Current password** to authenticate SSH and `sudo`.
- **Jump host**: `10.10.70.96` (key auth or password `!QAZ2wsx`). The jump host has `sshpass` 1.09 pre-installed, which is needed for nested password-based SSH.
- **New password**: Know the new value in advance. Avoid shell-special characters (`!`, `$`, `\`, backtick) unless properly quoted — use single quotes at the shell level.
- **Network**: SSH from the jump host to `192.168.12.12` over the private subnet.

## How to Run

Invoke through the `terminal` tool, executing on the jump host `10.10.70.96`:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.70.96 \
  "sshpass -p 'CURRENT_PASSWORD' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password jianliu@192.168.12.12 \
    'echo NEW_PASSWORD | sudo -S passwd --stdin jianliu'"
```

## Procedure

### 1. Verify current access

First, confirm SSH and sudo work with the current credentials:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.70.96 \
  "sshpass -p 'CURRENT_PASSWORD' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=5 jianliu@192.168.12.12 \
    'echo CURRENT_PASSWORD | sudo -S id && hostname'"
```

Expect: `uid=0(root)` and `h100-SYS-821GE-TNHR`.

### 2. Change the password

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.70.96 \
  "sshpass -p 'CURRENT_PASSWORD' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password jianliu@192.168.12.12 \
    'echo \"jianliu:NEW_PASSWORD\" | sudo -S chpasswd'"
```

The `chpasswd` command reads `username:password` pairs from stdin. `echo "jianliu:NEW_PASSWORD" | sudo -S chpasswd` sets jianliu's password atomically.

### 3. Verify the new password

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.70.96 \
  "sshpass -p 'NEW_PASSWORD' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=5 jianliu@192.168.12.12 \
    'hostname && ls /home/public/models/deepseekv4-flash/ 2>&1 | head -3'"
```

## Quick Reference

| Step | Command | Purpose |
|------|---------|---------|
| Verify | `ssh ... echo CURRENT_PASSWORD \| sudo -S id` | Confirm sudo access |
| Change | `ssh ... echo "jianliu:NEW" \| sudo -S chpasswd` | Set new password |
| Verify | `ssh ... sshpass -p 'NEW' ssh jianliu@12.12 hostname` | Confirm new password works |

## Pitfalls

- **Password with shell-special characters** — `qs@2024.local` contains `@` and `.` which are safe in single quotes. For passwords with `!`, `$`, or `\`, always wrap in single quotes `'...'` to prevent bash history expansion (`!`) and variable substitution (`$`). NEVER use double quotes for passwords containing `$` or `!`.
- **`sudo -S`** reads the password from stdin as a plain string. If the password ends with a newline-like character or has leading/trailing whitespace, `sudo` will silently fail. Test the password with a simple `echo password | sudo -S echo ok` first.
- **`chpasswd` vs `passwd`**: `passwd` is interactive (prompts for old + new password). `chpasswd` reads `username:newpassword` from stdin and is script-friendly. Always prefer `chpasswd` for automated password changes.
- **`sshpass` is required on the jump host** — `10.10.70.96` has it (`/usr/bin/sshpass` v1.09). The Hermes host does NOT have `sshpass` installed. Always route password-based SSH through 70.96.
- **Path difference**: The model directory on 12.12 is `/home/public/models/` (not `/data/models/` like the 10.10.70.x cluster). `deepseekv4-flash` is served from `/home/public/models/deepseekv4/`.
- **This node runs 8× H100 80GB** (driver 580.95.05), not Blackwell/warpdrive hardware. Standard `nvidia-smi` works — no stub issues.

## Verification

After changing the password, confirm the new credentials work end-to-end:

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.70.96 \
  "sshpass -p 'NEW_PASSWORD' ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o ConnectTimeout=5 jianliu@192.168.12.12 \
    'hostname'"
```

Expected output: `h100-SYS-821GE-TNHR`
