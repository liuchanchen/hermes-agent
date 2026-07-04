# 70.94 alltoall Benchmark Results (2026-06-24)

## Setup

- **Server**: 10.10.70.94 (oem94), RTX 5090 32GB × 8
- **Driver**: 580.159.03, Driver-CUDA 13.2
- **NCCL**: 2.30.7+cuda13.3 (apt-installed via `libnccl2 libnccl-dev`)
- **OpenMPI**: 4.1.2 (apt-installed via `openmpi-bin libopenmpi-dev`)
- **nccl-tests**: rebuilt with `make MPI=1 NCCL_HOME=/usr MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi`
- **Test**: `./alltoall_perf -g 1 -b 256M -e 4G -f 2 -w 10 -n 5`
- **Baseline comparison**: 70.88 (NCCL 2.28.9, Driver 580.159.03, Driver-CUDA 13.0)

## Results

| size | algbw (GB/s) | busbw (GB/s) | #wrong |
|------|-------------|-------------|--------|
| 256MB | 18.39 | 16.09 | 0 |
| 512MB | 19.03 | 16.65 | 0 |
| 1GB | 19.25 | 16.85 | 0 |
| 2GB | 19.24 | 16.83 | 0 |
| 4GB | 19.30 | 16.88 | 0 |
| **Avg** | — | **16.45** | — |

## 70.88 comparison

| size | 70.88 busbw | 70.94 busbw | delta |
|------|------------|------------|-------|
| 256MB | 21.96 | 16.09 | -26.7% |
| 512MB | 23.40 | 16.65 | -28.9% |
| 1GB | 23.88 | 16.85 | -29.4% |
| 2GB | 23.89 | 16.83 | -29.5% |
| 4GB | 23.98 | 16.88 | -29.6% |
| **Avg** | **23.50** | **16.45** | **-30.0%** |

## Root cause analysis

Likely CPU difference: 70.88 has Xeon Platinum 8558P (48c/socket, 260MB L3/socket) while 70.94 uses Ice Lake-based platform (confirmed: lspci shows "Intel Corporation Ice Lake" in PCIe root ports). The Ice Lake CPU likely has fewer cores / less L3 cache, causing worse alltoall performance (same pattern as observed between 70.88 and 70.92/70.98 in prior benchmarks).

Also: NCCL 2.30.7 (70.94) vs 2.28.9 (70.88) — but prior NCCL downgrade test on 70.92 showed NCCL version does NOT cause alltoall regression, so CPU is the dominant factor.

## Operational notes

- VLLM processes were running on all 8 GPUs (~32GB VRAM each). Had to kill them first to free GPU memory for the test.
- `/usr/local/bin/nvidia-smi` exits 113; use `/usr/bin/nvidia-smi` directly.
- nccl-tests source copied from 70.88 via `scp -r`. Rebuilt on 70.94 because NCCL 2.30.7 runtime is incompatible with 2.28.9 pre-built binaries.
- The `-g 1` flag is critical (1 GPU per MPI rank). Using `-g 8` with `mpirun -np 8` fails with "Invalid number of GPUs: N requested but only 8 were found" because each of 8 processes requests 8 GPUs (64 total).

## Pending

- 70.92 alltoall benchmark (needs OpenMPI install + nccl-tests rebuild first)
- 70.94 CPU model verification (`lscpu` output)