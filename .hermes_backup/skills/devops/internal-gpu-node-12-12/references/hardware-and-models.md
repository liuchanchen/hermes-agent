# 192.168.12.12 — Hardware & Model Inventory (2026-07-18)

## Hardware

| Property | Value |
|----------|-------|
| IP | 192.168.12.12 |
| GPU | 8× NVIDIA H100 80GB HBM3 |
| GPU Memory | 81,559 MiB per GPU |
| Power Limit | 700W per GPU |
| GPU Architecture | Hopper (not Blackwell) |
| nvidia-smi | Standard (no stub/wrapper issue) |
| OS | Linux (unidentified, no SSH access) |

## Running Services

| Port | Service | Status |
|------|---------|--------|
| 19258 | vLLM v0.20.0 — deepseekv4-flash | ✅ Healthy |
| 51653 | Secondary vLLM instance | ❌ Dead (connection reset) |
| 8080 | GPU monitoring dashboard (Python HTTP server) | ✅ Healthy |

## Model Storage

- **Model served**: deepseekv4-flash
- **Model root** (from vLLM API): `/home/public/models/deepseekv4/`
- **Max model len**: 1,048,576 tokens
- **Two model directories**: `/home/public/models/deepseekv4/` (serving, ~158GB) and `/home/public/models/deepseekv4-flash-0731/` (download in progress, ~158GB)
- **No /data/models/ directory** — this is NOT a 10.10.70.x server with shared storage
- **No NFS mounts** — local storage only (7.0TB overlay, 2.2TB free as of 2026-08-02)
- **GPU monitoring data** lives at `/data/gpu_history.csv` and `/data/snapshots/<date>.json` (accessible via port 8080 web server)

## Models NOT on this node

Despite being part of the same network, this node does NOT have:
- `glm_5_2_nvfp4` (433GB, on 70.96)
- `glm_5_1_nvfp4` (on 70.96)
- `glm_5_2_fp8` (on 70.96)
- `minimax_m2_7` / `minimax_m2_7_nvfp4` (on 70.95, 70.96)
- `deepseekv4_pro` (on 70.96/70.98, PP=2)
- `Qwen3.6-35B-A3B-FP8` (on 70.88)

## SSH Access

Password `!QAZ2wsx` for jianliu (confirmed working 2026-08-02). Use `sshpass -p '!QAZ2wsx' ssh jianliu@192.168.12.12`. The conda init on the host's `.bashrc` is broken — every SSH without `-T` produces conda TypeErrors. **Always use `ssh -T`** for clean output from container commands.

## GPU Usage Pattern (from monitoring data, July 18)

- Idle GPU memory: ~76,900 MB / 81,559 MB (94% — model loaded but idle)
- Peak utilization: ~99% during inference
- Power at idle: ~161W per GPU
- Power under load: ~258W per GPU (can hit 700W limit)
- Snapshot frequency: every 5 minutes
- Data available from June 22 onward
