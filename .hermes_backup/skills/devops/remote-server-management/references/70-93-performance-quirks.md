# 10.10.70.93 (oem93) — WarpDrive TGU01-Pro Appliance

**GPU:** 8× WarpDrive TGU01-Pro (32GB each, firmware 580.159.03)
**Driver:** WarpDrive UNIX Open Kernel Module 580.159.03
**System:** openEuler 24.03 (LTS-SP3)
**Kernel:** (openEuler default)
**Authentication:** Password only (`!QAZ2wsx` for jianliu sudo)
**NIC:** 2× Mellanox ConnectX-6 Dx (MT2892) — RoCE/RDMA capable

## WarpDrive vs Standard NVIDIA — Key Differences

### nvidia-smi is blocked
`/usr/local/bin/nvidia-smi` is a **stub shell script** installed by the "xplatform" WarpDrive platform:

```bash
#!/bin/bash
# xplatform-wrapper-marker
# Installed as the blocked GPU entry in /usr/local/bin or ~/.local/bin.
#
# This entry is intentionally blocked in favor of wd-smi.
exit 113
```

**Use `wd-smi` instead.** Output format is similar to nvidia-smi:

```
$ wd-smi
Driver Version: 2.8.0 | WD Version: 2.8.0

TGU Snapshot
  TGU  NAME         | BUS-ID          | FAN   | TEMP   | PERF | PWR            | MEM     
  #0  TGU01-Pro    | 00000000:16:00.0 | 43    | 25     | P8   |   11.98/575.00 |       1/32607   
  #1  TGU01-Pro    | 00000000:27:00.0 | 42    | 25     | P8   |   16.31/575.00 |       1/32607   
  ...
```

Each TGU01-Pro has 32607 MiB (~32 GB) memory. Device files: `/dev/nvidia0` through `/dev/nvidia7`, `/dev/nvidiactl`, `/dev/nvidia-modeset`, `/dev/nvidia-uvm`, `/dev/nvidia-caps/warpdrive-cap{1,2}`.

### Host-level software stack
- **No CUDA toolkit** on host (no `nvcc`, no `/usr/local/cuda`)
- **No NCCL** on host (no `libnccl` in `/usr/lib64/`)
- **No nvidia-smi** (blocked stub)
- **NVIDIA Container Toolkit** 1.19.0 installed (for Docker GPU passthrough)
- **WarpDrive platform** at `/opt/v3/current/` (docker-compose, data, my.cnf)

### Docker containers (as of 2026-06-24)
| Container | Image | Notes |
|-----------|-------|-------|
| `deepseek-v4-flash` | `nvidia/cuda:13.0.0-cudnn-devel-ubuntu24.04` | NCCL 2.27.7-1+cuda13.0, libnccl at `/usr/lib/x86_64-linux-gnu/libnccl.so.2.27.7` |
| `qs_wdtgu01_20000` | `10.10.91.56/sw2/wdtgu01` | WarpDrive internal service |
| `ai_webui` | `aiworkflow/webui:v3.0` | AI workflow UI |
| `ai_backend` | `aiworkflow/server:v3.0` | AI workflow backend |
| `ai_mysql` | `aiworkflow/database:v3.0` | MySQL database |
| `ai_redis` | `aiworkflow/redis:v3.0` | Redis cache |

To check NCCL inside a container:
```bash
docker exec deepseek-v4-flash dpkg -l libnccl2
```

## SSH Access

- Use full IP `10.10.70.93` (shorthand `70.93` resolves to wrong IP `70.0.0.92`)
- Password auth: `!QAZ2wsx` for sudo
- No SSH key configured for jianliu (unlike 70.88/70.92/70.96)

## User Accounts

| User | UID | Groups | Password | Notes |
|------|-----|--------|----------|-------|
| jianliu | 1002 | sudo | !QAZ2wsx | Primary admin |

## Pitfalls

- **`nvidia-smi` hangs then exits 113**: This is the xplatform stub. Use `wd-smi` instead. Same issue existed on 70.92 (fixed 2026-06-22 by removing the stub).
- **No host CUDA toolkit**: Cannot compile or run CUDA programs on the host. All GPU work runs inside Docker containers.
- **NCCL only in containers**: Host has no NCCL. To check NCCL version, inspect the running container: `docker exec <container> dpkg -l libnccl2`
- **`lsmod | grep nvidia` returns nothing**: The WarpDrive kernel module uses a different name. GPU devices are still accessible via `/dev/nvidia*`.
- **openEuler, not Ubuntu**: Uses `rpm`/`dnf` instead of `apt`/`dpkg`. Container images are Ubuntu-based, but the host is openEuler.
