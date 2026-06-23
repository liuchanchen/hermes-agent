# Server 70.92 (oem92) — Setup Notes

## Hardware
- **GPU:** 8× NVIDIA GeForce RTX 5090 32GB (SM 12.0 Blackwell)
- **CPU:** 2× Intel Xeon Gold 6530 (32c/64t per socket, 160 MB L3 per socket)
- **NUMA:** 2 nodes — GPU0-3 on NUMA0, GPU4-7 on NUMA1
- **Driver:** 595.71.05 / CUDA 13.2
- **OS:** Ubuntu 22.04.1 LTS
- **No NVLink** — confirmed by `nvidia-smi nvlink --status`
- **PCIe:** Gen5 ×16, same topology as 70.88/70.98

## Software Setup

### NCCL
- **Current:** NCCL 2.28.9+cuda13.0 (downgraded from 2.30.4 on 2026-06-22 for A/B testing)
- Library: `/usr/lib/x86_64-linux-gnu/libnccl.so.2.28.9`
- Previously had 2.30.4+cuda13.2 — downgraded to match 70.88 for alltoall comparison
- Install method: `apt-get install -y --allow-downgrades libnccl2=2.28.9-1+cuda13.0 libnccl-dev=2.28.9-1+cuda13.0`

### CUDA Toolkit
- Installed `cuda-toolkit-13-2` (nvcc at `/usr/local/cuda-13.2/bin/nvcc`)
- Build ID: `cuda_13.2.r13.2/compiler.37668154_0`

### nccl-tests
- Source copied from 70.88, then **rebuilt on 70.92** against local NCCL
- Path: `~/work/bandwidth_test/nccl-tests/`
- Build command: `make clean MPI=0 && make -j8 MPI=0 CUDA_HOME=/usr/local/cuda-13.2`
- **IMPORTANT:** Pre-built binaries from 70.88 (NCCL 2.28.9 headers) are NOT compatible with NCCL 2.30.4+ runtime — Device API changed at 2.29. Always rebuild on the target server.

### nvidia-smi Fix
- `/usr/local/bin/nvidia-smi` was a fake wrapper script that did `exit 113`
  - Installed by "xplatform" to block nvidia-smi in favor of `wd-smi`
  - Shadowed the real binary at `/usr/bin/nvidia-smi` (earlier in PATH)
  - Fix: `sudo rm /usr/local/bin/nvidia-smi`
  - Check other servers for same issue if `nvidia-smi` returns exit code 113

### vLLM / DeepSeek-V4-Flash
- **Model path:** `/home/public/models/tgu01/deepseekv4_flash/` (149GB, 46 safetensors)
- **vLLM venv:** `/data/venvs/vllm-ds4/` — copied from 70.88 on 2026-06-22
  - **Python 3.12 required** — venv was built with Python 3.12 but 70.92 only has Python 3.10 by default
  - Need to install Python 3.12: `sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt-get install -y python3.12 python3.12-venv python3.12-dev`
- **Startup script:** `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`
  - Script references `/data/models/deepseekv4_flash` — need symlink: `sudo ln -s /home/public/models/tgu01/deepseekv4_flash /data/models/deepseekv4_flash`
  - Or change `MODEL_PATH` in the script
- **Previously running config (killed 2026-06-22):** TP=8, EP enabled, port 8844, max_model_len=40960, kv-cache=fp8, block-size=256

## Access
- **SSH:** `ssh jianliu@10.10.70.92` (key auth works)
- **No proxy** — direct internet access
- **sudo:** requires password (`!QAZ2wsx`)
- **`/data/` ownership:** `rapidsdb:rapidsdb` — jianliu cannot write. Use `sudo mkdir` + `sudo chown jianliu:jianliu`.

## Alltoall Benchmarks (2026-06-22)

### NCCL 2.28.9+cuda13.0 (post-reboot, final)

| Size | 4-GPU busbw | 8-GPU busbw | 8/4 ratio |
|------|------------|------------|-----------|
| 8K   | 0.31       | 0.10       | 0.32x     |
| 64K  | 2.26       | 0.75       | 0.33x     |
| 512K | 9.99       | 4.88       | 0.49x     |
| 1M   | 11.35      | 5.80       | 0.51x     |
| 4M   | 13.03      | 6.92       | 0.53x     |
| 16M  | 16.56      | 8.22       | 0.50x     |
| 64M  | 17.93      | 13.00      | 0.73x     |
| 256M | 18.79      | 12.46      | 0.66x     |
| Avg  | 6.42       | 3.71       | 0.58x     |

Peak 4-GPU: 25.05 GB/s @ 256M. Peak 8-GPU: 13.00 GB/s @ 64M.

### NCCL 2.30.4+cuda13.2 (before downgrade)

| Size | 4-GPU busbw | 8-GPU busbw | 8/4 ratio |
|------|------------|------------|-----------|
| 8K   | 0.20       | 0.09       | 0.45x     |
| 64K  | 1.50       | 0.68       | 0.45x     |
| 512K | 10.00      | 4.85       | 0.49x     |
| 1M   | 11.16      | 6.24       | 0.56x     |
| 4M   | 12.83      | 7.52       | 0.59x     |
| 16M  | 16.42      | 9.87       | 0.60x     |
| 64M  | 17.92      | 12.75      | 0.71x     |
| 256M | 18.87      | 12.36      | 0.65x     |
| Avg  | 6.20       | 3.98       | 0.64x     |

Peak 4-GPU: 18.87 GB/s @ 256M. Peak 8-GPU: 12.75 GB/s @ 64M.

### A/B Test Conclusion

**NCCL version is NOT the cause of alltoall performance differences.** 70.92 with NCCL 2.28.9 gets 12.46 GB/s 8-GPU peak at 256M, while NCCL 2.30.4 got 12.36 GB/s — essentially identical. The dominant factor is CPU: 70.88's Xeon Platinum 8558P (48c, 260MB L3) achieves 25.25 GB/s vs ~12.5 GB/s on the Xeon Gold 6530 servers.
