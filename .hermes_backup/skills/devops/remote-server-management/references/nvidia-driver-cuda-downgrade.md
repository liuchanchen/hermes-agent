# NVIDIA Driver & CUDA Toolkit Downgrade Procedure (Ubuntu 22.04)

## Overview

Procedure for downgrading NVIDIA driver + CUDA toolkit on Ubuntu 22.04 to match a target server's configuration. Captured from downgrading 70.92 (595.71.05 / CUDA 13.2) to match 70.88 (580.159.03 / CUDA 13.0).

## Key Differences Between 595 and 580 Driver Series

| Aspect | 595 Series | 580 Series |
|--------|-----------|-----------|
| Typical package | `nvidia-driver-595-open` | `nvidia-driver-580-server-open` |
| Ubuntu repo | `jammy-updates/restricted` | `jammy-updates/restricted` |
| CUDA Toolkit meta | `cuda-toolkit-13-2` → CUDA 13.2.1 | `cuda-toolkit-13-0` → CUDA 13.0.3 |
| Server 70.88 | — | 580.159.03 |
| Server 70.92 | 595.71.05 (to be replaced) | target: 580.159.03 |

## Step-by-Step Downgrade Procedure

### 1. Pre-flight: Check current state and available packages

```bash
# Current driver version
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1

# Current CUDA toolkit version
/usr/local/cuda/bin/nvcc --version

# List all installed nvidia packages (Ubuntu apt)
dpkg -l | grep -iE 'nvidia|cuda' | awk '{print $2, $3}' | sort

# Check target package availability
apt-cache policy nvidia-driver-580-server-open
apt-cache policy cuda-toolkit-13-0
```

### 2. Stop GPU workloads

```bash
# Find any vLLM or other GPU processes
ps aux | grep -i vllm
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader

# Kill GPU processes (confirm PID list first)
kill -9 <PID1> <PID2> ...
# Verify freed
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
```

### 3. Remove existing driver + CUDA toolkit packages

```bash
# Remove 595 driver packages
sudo apt-get remove --purge -y \
  nvidia-driver-595-open \
  nvidia-utils-595 \
  nvidia-dkms-595-open \
  nvidia-kernel-common-595 \
  libnvidia-compute-595 \
  libnvidia-common-595 \
  libnvidia-cfg1-595 \
  libnvidia-decode-595 \
  libnvidia-encode-595 \
  libnvidia-extra-595 \
  libnvidia-fbc1-595 \
  libnvidia-gl-595 \
  nvidia-compute-utils-595 \
  nvidia-firmware-595-*

# Remove CUDA 13-2 toolkit packages
sudo apt-get remove --purge -y \
  cuda-toolkit-13-2 \
  cuda-toolkit-13-2-config-common \
  cuda-command-line-tools-13-2 \
  cuda-compiler-13-2 \
  cuda-cudart-13-2 \
  cuda-cudart-dev-13-2 \
  cuda-nvcc-13-2 \
  cuda-nvrtc-13-2 \
  cuda-nvrtc-dev-13-2 \
  cuda-nvtx-13-2 \
  cuda-cupti-13-2 \
  cuda-cupti-dev-13-2 \
  cuda-gdb-13-2 \
  cuda-libraries-13-2 \
  cuda-libraries-dev-13-2 \
  cuda-sanitizer-13-2 \
  cuda-tools-13-2 \
  cuda-visual-tools-13-2 \
  cuda-nsight-13-2 \
  cuda-nsight-compute-13-2 \
  cuda-nsight-systems-13-2 \
  cuda-documentation-13-2 \
  cuda-driver-dev-13-2 \
  cuda-cccl-13-2 \
  cuda-crt-13-2 \
  cuda-culibos-dev-13-2 \
  cuda-cuobjdump-13-2 \
  cuda-cuxxfilt-13-2 \
  cuda-nvdisasm-13-2 \
  cuda-nvml-dev-13-2 \
  cuda-nvprune-13-2 \
  cuda-opencl-13-2 \
  cuda-profiler-api-13-2 \
  cuda-sandbox-dev-13-2 \
  cuda-tileiras-13-2 \
  libcufile-13-2 \
  libcusolver-13-2 \
  libcusolver-dev-13-2 \
  libnvptxcompiler-13-2 \
  libnvvm-13-2 \
  nsight-compute-2026.1.1 \
  xserver-xorg-video-nvidia-595

# Also remove nvidia-utils-595 transitional package if present
sudo apt-get autoremove --purge -y

# Clean symlinks and old CUDA directories
sudo rm -f /usr/local/cuda /usr/local/cuda-13 2>/dev/null
sudo rm -rf /usr/local/cuda-13.2 2>/dev/null
```

### 4. Install target driver + CUDA toolkit

```bash
# Install 580 server driver (open kernel module variant)
sudo apt-get install -y nvidia-driver-580-server-open

# Install CUDA 13.0 toolkit (matches 70.88)
sudo apt-get install -y cuda-toolkit-13-0

# Verify packages installed
dpkg -l | grep -iE 'nvidia.*580|cuda.*13-0' | awk '{print $2, $3}'
```

### 5. Reboot

```bash
sudo reboot
```

### 6. Post-reboot verification

```bash
# Verify driver
nvidia-smi --query-gpu=index,name,driver_version --format=csv,noheader

# Expected output:
# driver_version = 580.159.03
# CUDA Version = 13.0

# Verify all GPUs recognized
nvidia-smi --query-gpu=count --format=csv,noheader

# Verify nvcc
/usr/local/cuda/bin/nvcc --version
# Expected: release 13.0, V13.0.88

# Verify nvidia-smi version consistency
nvidia-smi --version
# Expected: all 3 components match (NVIDIA-SMI, NVML, DRIVER = 580.159.03)
```

## SMI Version vs Driver Version Mismatch

On 70.92 before downgrade, `nvidia-smi` showed:
```
NVIDIA-SMI version  : 580.159.03   ← old embedded string
DRIVER version      : 595.71.05    ← actual loaded kernel module
NVML version        : 595.71       ← actual NVML library
```

This **mismatch is cosmetic only** — the nvidia-smi binary's "NVIDIA-SMI version" is a compile-time embedded string that may not update with the package version. Even though `rpm -qf` / `dpkg -S` confirmed the binary came from the correct `nvidia-utils-595` package, the version string in the binary itself still said 580.159.03.

**When NOT to worry about the mismatch:**
- `DRIVER version` matches the kernel module (always authoritative)
- `NVML version` is close to the driver version (595.71 vs 595.71.05)
- All nvidia-smi queries return valid results
- GPU workloads (vLLM) run normally

**After downgrade, all three fields should match** (580.159.03), confirming clean installation.

## Pitfalls

- **This is a destructive operation** — GPU workloads will be down for ~10 minutes during removal + install + reboot
- **`cuda-keyring` package remains** — DO NOT remove it; it's the apt source that provides all CUDA repos
- **`libnccl2` package may be CUDA-version specific** — check compatibility. On 70.92, `libnccl2=2.28.9-1+cuda13.0` was already compatible with both CUDA 13.0 (70.88) and CUDA 13.2 (70.92). If NCCL was installed via `cuda-toolkit-13-2` packages, it will be removed automatically; reinstall with `apt-get install libnccl2=2.28.9-1+cuda13.0` after downgrade.
- **nvidia-container-toolkit is independent** — container runtime packages (`nvidia-container-toolkit`, `libnvidia-container*`) don't need to be removed/reinstalled. They work with any driver version.
- **Don't remove `cuda-keyring`** — it's architecture-independent and version-inspecific; removing it breaks apt access to NVIDIA repos.
- **Kernel headers needed for DKMS** — ensure `linux-headers-$(uname -r)` is installed before installing the new driver, or DKMS build will fail.
