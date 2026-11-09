---
name: rdma-gdr-benchmarking
description: Benchmark RoCE RDMA bandwidth, latency, and GDR capability.
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [RDMA, RoCE, GPUDirect, NCCL, Perftest, Benchmarks]

---

# RDMA and GPUDirect RDMA Benchmarking

Benchmark RoCEv2 RDMA bandwidth (ib_write_bw, ib_read_bw) and latency (ib_write_lat) between TGU nodes, plus verify GPUDirect RDMA capability with `query_cuda_gdr.c`. Also covers building CUDA-enabled perftest binaries and generating NCCL environment variables for RDMA transport.

These are network micro-benchmarks using host memory or GPU device memory. They are **not** NCCL collective communication results — those require a separate maintenance window with all GPUs released.

## When to Use

- User asks to test or verify RoCE RDMA bandwidth between two servers.
- User asks whether GPUDirect RDMA works on a given GPU model.
- User needs to validate CUDA GDR capability flags (`GPU_DIRECT_RDMA_SUPPORTED`, `DMA_BUF_SUPPORTED`) on a host.
- User needs to rebuild perftest with CUDA support.
- User asks for NCCL environment variable settings for RDMA.

## Prerequisites

- SSH access to both servers (jianliu user, key auth).
- RDMA-capable NICs (Mellanox ConnectX/mlx5) with RoCEv2 configured.
- For GDR tests: `nvidia_peermem` kernel module loaded, perftest built with `--enable-cudart`.
- `enable_and_test_rdma.sh` script present on both hosts (canonical location: wherever the user has it).

## How to Run

Invoke through the `terminal` tool. Typical workflow: check status → enable RDMA link → start server on peer → run client → print NCCL env vars.

## Quick Reference

| Command | Description |
|---------|-------------|
| `enable_and_test_rdma.sh check` | Show HCA/interface state |
| `enable_and_test_rdma.sh enable` | Load modules, set IP/MTU, bring link up |
| `enable_and_test_rdma.sh server` | Start perftest server |
| `enable_and_test_rdma.sh client <ip>` | Run perftest against peer |
| `enable_and_test_rdma.sh nccl-env` | Print NCCL env vars for current HCA |
| `/tmp/query_cuda_gdr` | Check CUDA GDR capabilities per GPU |
| `gcc query_cuda_gdr.c -lcuda -o /tmp/query_cuda_gdr` | Compile GDR capability checker |

## Procedure

### 1. Check RDMA status on both hosts

```bash
ssh jianliu@<host> "cd ~/work/... && bash enable_and_test_rdma.sh check"
```

On `oem88` (ens35f0np0/mlx5_0/port 1), on `oem98` (bond0/mlx5_1/port 1).

### 2. Enable RDMA link (first-time or after reboot)

```bash
# oem88
ssh jianliu@10.10.68.88 "cd ~/work/... && GID_INDEX=3 bash enable_and_test_rdma.sh enable"

# oem98 (address on bond0/mlx5_1)
ssh jianliu@10.10.68.98 "cd ~/work/... && RDMA_IFACE=bond0 RDMA_HCA=mlx5_1 GID_INDEX=3 bash enable_and_test_rdma.sh enable"
```

### 3. Run RDMA bandwidth test (ib_write_bw)

On the **peer** first, start server:

```bash
ssh jianliu@10.10.68.98 "cd ~/work/... && RDMA_IFACE=bond0 RDMA_HCA=mlx5_1 GID_INDEX=3 bash enable_and_test_rdma.sh server"
```

Then on the **initiator**, run client:

```bash
ssh jianliu@10.10.68.88 "cd ~/work/... && GID_INDEX=3 bash enable_and_test_rdma.sh client 10.10.68.98"
```

Direct perftest commands (useful for custom parameters):

```bash
# Server (oem98)
ib_write_bw -d mlx5_1 -i 1 -x 3 -F --report_gbits -D 10

# Client (oem88)
ib_write_bw -d mlx5_0 -i 1 -x 3 -F --report_gbits -D 10 10.10.68.98
```

### 4. Run RDMA latency test

```bash
# oem98 (server)
ib_write_lat -d mlx5_1 -i 1 -x 3 -F -s 8 -n 10000

# oem88 (client)
ib_write_lat -d mlx5_0 -i 1 -x 3 -F -s 8 -n 10000 10.10.68.98
```

### 5. Check CUDA GPUDirect RDMA capability

Compile and run the checker on the target host:

```bash
ssh jianliu@<host> "gcc -O2 -Wall -I/usr/local/cuda/include ~/work/.../query_cuda_gdr.c -L/usr/lib/x86_64-linux-gnu -lcuda -o /tmp/query_cuda_gdr && /tmp/query_cuda_gdr"
```

Expected output per GPU:
- `GPU_DIRECT_RDMA_SUPPORTED` = 1 (GDR-capable GPU, e.g. RTX PRO 6000)
- `DMA_BUF_SUPPORTED` = 1
- `ALLOCATED_POINTER_GDR_CAPABLE` = 1
- RTX 5090 reports 0 for all three (not GDR-capable).

### 6. GPUDirect RDMA test (GDR-capable GPUs only)

On the peer with a GDR-capable GPU (e.g. oem98 RTX PRO 6000):

```bash
# Server with CUDA device 4
ssh jianliu@10.10.68.98 "LD_LIBRARY_PATH=/tmp/perftest-gdr/lib:\${LD_LIBRARY_PATH:-} /tmp/perftest-gdr/ib_write_bw -d mlx5_1 -i 1 -x 3 -F --report_gbits -D 10 --use_cuda=4"
```

On the initiator (host memory source):

```bash
ssh jianliu@10.10.68.88 "/tmp/perftest-gdr/ib_write_bw -d mlx5_0 -i 1 -x 3 -F --report_gbits -D 10 10.10.68.98"
```

Do **not** add `--use_cuda=N` on oem88 (RTX 5090) — it will fail with `ibv_reg_mr EFAULT(14)` because CUDA marks those allocations as not GDR-capable.

### 7. Build CUDA-enabled perftest (one-time per host)

```bash
ssh jianliu@<host> "bash ~/work/.../build_cuda_perftest.sh"
```

This clones the official linux-rdma/perftest repo at commit `4c260cb26`, auto-fetches `libpci-dev`, configures with `--enable-cudart`, and installs binaries to `/tmp/perftest-gdr/`.

### 8. Generate NCCL environment variables for RDMA

```bash
ssh jianliu@10.10.68.88 "cd ~/work/... && GID_INDEX=3 bash enable_and_test_rdma.sh nccl-env"

# Example output:
#   export NCCL_IB_DISABLE=0
#   export NCCL_IB_HCA==mlx5_0:1
#   export NCCL_SOCKET_IFNAME==ens20f0
#   export NCCL_DEBUG=INFO
#   export NCCL_DEBUG_SUBSYS=INIT,NET
#   export NCCL_IB_GID_INDEX=3
```

Load into shell with: `eval "$(bash enable_and_test_rdma.sh nccl-env)"`

## Pitfalls

- **Do not use `-R` (RDMA-CM)** when the peer uses a bond interface — bond devices reject RDMA-CM connection setup. The `enable_and_test_rdma.sh` script defaults `USE_RDMA_CM=0`. Remove `-R` from manual perftest commands if the peer has a bond.
- **RTX 5090 does NOT support GPUDirect RDMA.** CUDA reports `GPU_DIRECT_RDMA_SUPPORTED=0`, `DMA_BUF_SUPPORTED=0`, and `ALLOCATED_POINTER_GDR_CAPABLE=0` for all 8 GPUs. Adding `--use_cuda=N` on these cards will produce `ibv_reg_mr: EFAULT (14)`. Only RTX PRO / datacenter GPUs (e.g. RTX PRO 6000 Blackwell) are GDR-capable.
- **Loading `nvidia_peermem` is necessary but not sufficient** for GPU-to-GPU RDMA. The CUDA device capability check must also return 1; `nvidia_peermem` alone cannot override a 0-capability GPU.
- **Stale `nvidia_peermem` modules** may have been compiled against wrong kernel headers, resulting in an empty stub that returns `-EINVAL` on load. Rebuild with matching MLNX_OFED headers. The correct module depends on `nvidia` and `ib_uverbs` and exports `ib_register_peer_memory_client`, `nvidia_p2p_get_pages`, etc.
- **System perftest binaries reject CUDA buffers** with `Unsupported memory type`. Always use a CUDA-enabled build from `/tmp/perftest-gdr/` for GDR tests.
- **Ensure `OMP_NUM_THREADS=1`** in the environment when running perftest on the same host that runs vLLM (vLLM reduces Torch parallelism to 1 thread; perftest may oversubscribe CPUs otherwise).
- **`nvidia-smi` may exit with code 113** on some TGU hosts; this is normal for these platforms. CUDA driver API still works for perftest GDR tests.

## Verification

After configuring RDMA, a successful check should show:

```bash
# Both directions reach 92.57 Gbit/s on a 100-Gbit RoCE link
ib_write_bw -d mlx5_0 -i 1 -x 3 -F --report_gbits -D 10 10.10.68.98
# Expected output: 92.57 Gbit/s (RC RDMA write, single QP)
```
