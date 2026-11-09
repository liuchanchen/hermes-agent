# 10.10.70.95 (oem95) — Config & VLLM Server

**GPU:** 8× NVIDIA RTX 5090 (Blackwell, CC 12.0, 32GB)
**Driver:** 595.58.03 | **CUDA Driver:** 13.2
**System:** Ubuntu 22.04.1 LTS | **Kernel:** 6.8.0-111-generic (newer! vs 93/96 5.15)
**Storage:** LVM (`/dev/mapper/vgubuntu-root`)

## Key Differences from 70.93

- **Has proxy** (`http://10.10.60.140:7890` in ~/.bashrc — same as 70.88)
- **Newer kernel** (6.8.0) — better Mellanox/RDMA support
- **LVM storage** — easier expansion

## SSH (proxy required)

```
ssh jianliu@10.10.70.95 "source ~/.bashrc && command"
```

Same proxy pattern as 70.88 — always source .bashrc.

## vLLM Environment

- Source: `/data/vllm-ds4-sm120/`

## Current vLLM Server (MiniMax M2 nvfp4)

| Field | Value |
|-------|-------|
| Model | `/data/models/minimax_m2_7_nvfp4` |
| Served name | `minimax_m2_7` |
| Port | 8000 |
| API Key | `***.95-vllm` (literal asterisks) |
| Startup script | `/data/venvs/vllm-ds4/start_minimax_m2_nvfp4_tpep.sh` |
| TP | 8 (tensor-parallel-size 8) |
| EP | Enabled (--enable-expert-parallel) |
| max-model-len | 262144 |
| max-num-seqs | 64 |
| kv-cache-dtype | fp8 |
| gpu-memory-util | 0.85 |
| compilation mode | 3, with `fuse_minimax_qk_norm=false` |
| Started | May 22 |
| Notes | No curl installed — use `/data/venvs/vllm-ds4/bin/python3` for HTTP tests |
- Venv: `/data/venvs/vllm-ds4/` (Python 3.12, PyTorch 2.11.0+cu130)
- CUDA dev packages installed (nvrtc, cublas, cusparse, cusolver)
