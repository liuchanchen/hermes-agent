---
name: fenghua-gpu-node-70-99
description: Access Fenghua GR308S FTUCA node 10.10.68.99.
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [68.99, Fenghua, GR308S, FTUCA, FANTGPU]
---

# Fenghua GR308S Node 10.10.68.99

> **⚠ STALE 2026-09-04 (live-verified):** 68.99 has been RE-IMAGED — it now runs **WarpDrive TGU01F** cards (2 GPU nodes, dual-die bus `0000:98:00.0/.2`, 56GB GDDR6 each) with driver `1.0.0.1 (2026.08.25)` and **`/usr/local/bin/warpdgpu-smi`** (GPU-SMI 1.0.0.1). No `fantgpu-smi`, no `wd-smi`, no NVIDIA stack. `/usr/local/warpd/` toolchain (hipcc etc.) installed. `warpdgpu-smi` does NOT support `--query-gpu` (CSV mode) — parse the default table output instead. The Fenghua content below applies only to the pre-2026-08-25 image.

68.99 (oem-99) was a **Fenghua (风华) GR308S MAX** node running the **FTUCA** software stack — NOT a WarpDrive/NVIDIA card. It exposes 16 GPU nodes from 8 physical GR308S MAX cards via `fantgpu-smi` (dual-die: 1 card = 2 GPU nodes), and has the FTUCA vLLM container images + K8s device-plugin/exporter stack preloaded. For the generic Fenghua FTUCA install/monitor/cluster procedures see the `fenghua-ftuca-quickstart` skill; this skill is the node-specific access + state reference. The old `remote-server-management` row describing 68.99 as "no NVIDIA driver, use wd-smi" is WRONG for this node — wd-smi does not exist here.

## When to Use

- SSHing into 10.10.68.99 and checking its GPU state
- Which GPU stack does 68.99 run? (answer: Fenghua GR308S MAX / FTUCA, not WarpDrive)
- Running vLLM inference on 68.99 with the FTUCA vLLM image
- Confirming K8s device-plugin / fantasy-exporter images present on 68.99
- Any task on 68.99 that would wrongly assume an NVIDIA driver (`nvidia-smi`) or `wd-smi`

## Prerequisites

- **SSH:** user `jianliu` / password `!QAZ2wsx` (verified 2026-08-06). Peer `id`: uid 1001, groups jianliu/sudo/docker.
- No `sshpass` locally — use the `pexpect-ssh.py` helper from the `remote-server-management` skill:
  `python3 <skill>/scripts/pexpect-ssh.py 10.10.68.99 jianliu '!QAZ2wsx' '<cmd>'`
- Keep remote commands simple: the pexpect wrapper mangles nested quotes, `{{ }}`, and `$( )`. One command per line, no complex quoting.
- GPU monitoring tool is `fantgpu-smi` (kernel/demo GH: it works without root). No `nvidia-smi`, no `wd-smi` on this node.

## How to Run

Invoke each GPU/container command through the `terminal` tool, wrapping in `pexpect-ssh.py` (see Prerequisites). Verify GPU state with `fantgpu-smi` before assuming any inference workload, and note the 8-card / 16-node breakdown.

## Quick Reference

```bash
# SSH (via pexpect-ssh.py, no local sshpass)
python3 <skill>/scripts/pexpect-ssh.py 10.10.68.99 jianliu '!QAZ2wsx' 'fantgpu-smi'

# GPU status (fantgpu-smi resembles nvidia-smi layout)
fantgpu-smi                                   # full status, 16 GR308 nodes
fantgpu-smi --loop xx --filename FILE        # refresh every xx sec, dump to file

# Loaded FTUCA images (as of 2026-08-06)
docker images
# 10.10.91.56/sw2/fantgpu-fh3/vllm            1.1.0.17-py310-ubuntu22.04   66f84f8e869a  5.78GB
# fantasy/vllm                                1.1.0.17-py310-ubuntu22.04   66f84f8e869a  5.78GB
# vllm                                        1.1.0.16-py310-ubuntu22.04   8c3ed6c1eeed  5.8GB
# 10.10.91.56/sw2/fantgpu-fh3/k8s-device-plugin  v1.0.0.7  30ff574ed4dc  97.8MB
# k8s-device-plugin                               v1.0.0.7  30ff574ed4dc  97.8MB
# 10.10.91.56/sw2/fantgpu-fh3/fantasy-exporter   v1.0.0.8  52b04392fc0f  98.2MB
# fantasy-exporter                               v1.0.0.8  52b04392fc0f  98.2MB

# installed FTUCA packages
dpkg -l | grep fantgpu
# fantgpu-container-toolkit 1.0.0.9, fantgpu-fh3 1.1.0.17-driver, fantgpu-fh3-fantrt 1.0.0.22,
# fantgpu-fh3-ftuca-libraries 1.1.0.17, fantgpu-fh3-ftuca-wheels 1.1.0.17,
# fantgpu-fh3-onnxruntime-wheels 1.0.0.22, fantgpu-smi 2.2.0.9-linux
```

## Procedure

1. **Verify GPU stack** (expect this output shape — no NVIDIA/wd-smi):
   ```bash
   command -v fantgpu-smi   # → /usr/local/bin/fantgpu-smi
   command -v wd-smi        # → (nothing)
   command -v nvidia-smi    # → (nothing)
   ```
2. **GPU health check** — `fantgpu-smi` shows 16 GR308 nodes (8 physical cards × 2 die). Card pair bus-IDs like `0000:16:00.0` / `0000:16:00.2` on the same PCIe card (PCI-E Gen5 x16). Each node: 56 GB VRAM (`540MiB / 57344MiB`), GDDR6 `1008.00GB/s`, 448-bit, firmware `1.0.1.45-firmware_cfg-3_FUD_DD_V4P1_20250925`. "No running processes found" = idle.
   ```bash
   fantgpu-smi
   ```
3. **Container / inference** — FTUCA vLLM images are loaded; `docker images` shows `vllm:1.1.0.17-py310-ubuntu22.04` (ID 66f84f8e869a, also tagged `fantasy/vllm` and `10.10.91.56/sw2/fantgpu-fh3/vllm`) and `vllm:1.1.0.16` (ID 8c3ed6c1eeed). The fantasy runtime is **default** (`docker info` → `Default Runtime: fantasy`), so **no `--gpus all` needed** — the FTUCA runtime injects GPUs. The image has **no default CMD/ENTRYPOINT**, so always supply the vLLM command yourself. Launch pattern verified from the node's own history (image 8c3ed6c1eeed, cont. `0cd113d05d9a`): runtime fantasy, not privileged, `--shm-size 16g`, bind `-v /home/public/models/tgu01:/media/models/`, command:
   ```bash
   docker run -d --name vllm-fh3 --restart unless-stopped \
     --runtime fantasy --shm-size 16g \
     -v /home/public/models/tgu01:/media/models \
     -p 8000:8000 \
     66f84f8e869a \
     /root/miniconda3/bin/vllm serve /media/models/MODEL \
     --served-model-name MODEL --tensor-parallel-size 8 \
     --gpu-memory-utilization 0.9 --max-model-len 204800 \
     --max-num-seqs 32 --trust-remote-code \
     --host 0.0.0.0 --port 8000
   ```
   (Prior container used TP=8 PP=2 EP with MiniMax-M2.7-BF16: `docker run -d --name vllm-old --runtime fantasy --shm-size 16g -v /home/public/models/tgu01:/media/models/ -p 8000:8000 8c3ed6c1eeed /root/miniconda3/bin/vllm serve /media/models/MiniMax-M2.7-BF16/ --tokenizer /media/models/MiniMax-M2.7-BF16/ --tensor-parallel-size 8 --pipeline-parallel-size 2 --dtype auto --enforce-eager --enable_expert_parallel --gpu-memory-utilization 0.9 --max-model-len 204800 --max-num-seqs 32 --no-enable-prefix-caching --trust-remote-code --host 0.0.0.0 --port 8000`.)
4. **K8s cluster awareness** — device-plugin + exporter images are already imported, so this node is K8s-plugin-ready. `fantasy.com/gpu` capacity will report 16 (registered GPU nodes), not 8 cards. See the quick-start's cluster section for yaml patterns (nodeAffinity, `fantasy.com/gpu` requests/limits, hostPath model mount).
5. **Monitoring** — for a rolling status snapshot use:
   ```bash
   fantgpu-smi --loop 5 --filename /tmp/smi.log
   ```
   Dump goes to the node's file; tail it via a second SSH call.

## Pitfalls

- **68.99 is Fenghua, not WarpDrive.** wd-smi / nvidia-smi do NOT exist here. The `remote-server-management` "Supported Servers" table's old 68.99 note about "use wd-smi" is stale — corrected 2026-08-06 to Fenghua GR308S / FTUCA.
- **16 GPU nodes = 8 cards.** 1 GR308S MAX = 2 GR308 GPU nodes (dual-die). Device plugin reports 16, and pod requests use `fantasy.com/gpu` counted in nodes, not cards. Don't request 8 when you mean 16 or vice-versa.
- **pexpect-ssh.py quoting limits**: avoid `$( )`, nested quotes, and `{{ }}` template braces in the remote command — the wrapper runs `bash -c "<cmd>"` with double quotes, so any double quote inside breaks the wrapping and `{{...}}` is then mis-parsed. **Fix:** keep commands single-line and use **single quotes** around `--format '{{...}}'` templates (single quotes survive the outer double quote). Verified 2026-08-06.
- **Driver 1.1.0.17 (2026.07.17)** is newer than the quick-start doc's example 1.1.0.10 — the dpkg packages (fantgpu-fh3 1.1.0.17, fantrt 1.0.0.22, ftuca 1.1.0.17) are what's actually installed; version strings in the generic guide's filenames should be read as 1.1.0.17 here.
- **All 16 nodes idle as of 2026-08-06** — "No running processes found"; don't assume a serving instance exists until you start one.

## Verification

```bash
python3 <skill>/scripts/pexpect-ssh.py 10.10.68.99 jianliu '!QAZ2wsx' 'fantgpu-smi | head -8'
```
Expect `GPU-SMI 2.2.0.9-linux` with `Driver Version(Release Time): 1.1.0.17` and GR308 entries — the definitive proof 68.99 is a Fenghua GR308S FTUCA node.
