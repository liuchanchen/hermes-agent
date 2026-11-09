---
name: nccl-forward-comm-benchmark
description: Benchmark expert-parallel NCCL dispatch via PCIe and RDMA.
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [NCCL, RDMA, Alltoall, DeepSeek, Expert-Parallel, Benchmarks]

---

# NCCL Forward Communication Benchmarking (PCIe + Cross-Server RDMA)

Benchmark real NCCL forward-pass communication patterns for DeepSeek V4 expert-parallel dispatch using `forward_comm_benchmark.py`. Covers PCIe host-to-device (H2D) / device-to-host (D2H) staging baselines, local GPU-to-GPU P2P, cross-server GPU-to-GPU P2P over RoCE, and 8/16-rank all-to-all for top-6 expert dispatch. Does **not** require GPUDirect RDMA (RTX 5090 hosts can still be tested via staged paths). The benchmark validates received data before measuring.

These are communication micro-benchmarks, not full vLLM inference benchmarks. They isolate the NCCL transfer cost without vLLM's scheduler, request queues, or compute/communication overlap.

## When to Use

- User wants to compare local vs cross-server NCCL all-to-all latency for DeepSeek V4 expert dispatch.
- User needs to measure PCIe H2D/D2H staging bandwidth on a GPU node.
- User wants to tune `NCCL_IB_QPS_PER_CONNECTION` (shown to cause performance cliffs at 512-token payloads).
- User needs to validate NCCL RDMA path before deploying expert-parallel vLLM.
- User encounters MTU mismatch between RoCE peers causing NCCL `WR work queue error` or `IBV_WC_REM_INV_REQ_ERR`.

## Prerequisites

- PyTorch with NCCL (v2.28.9 recommended for consistency across test nodes).
- `forward_comm_benchmark.py` script (369 lines, stdlib + torch).
- For cross-server tests: passwordless SSH, matching NCCL runtime on both hosts, RoCE RDMA connectivity.
- For MTU-mismatched fabric: patched NCCL build with `nccl_2.28.9_roce_receiver_mtu.patch` (one-line change in `src/transport/net_ib.cc`).
- Two GPU hosts with 8 GPUs each recommended for full 16-rank all-to-all.

## How to Run

Invoke through the `terminal` tool. PCIe baseline runs directly (`python3 forward_comm_benchmark.py --mode pcie`). P2P and all-to-all require `torchrun`. Cross-server tests need matching script and NCCL builds on both hosts, plus RDMA connectivity.

## Quick Reference

| Command | Mode | Scope |
|---------|------|-------|
| `python3 forward_comm_benchmark.py --mode pcie` | PCIe H2D/D2H | Single GPU + pinned host memory |
| `torchrun --nproc-per-node=2 forward_comm_benchmark.py --mode p2p` | Local GPU↔GPU P2P | Within same host |
| `torchrun --nproc-per-node=8 forward_comm_benchmark.py --mode alltoall` | Local all-to-all | 8-rank top-6 expert dispatch |
| `torchrun --nproc-per-node=8 --nnodes=2 ... --mode p2p` | Cross-server GPU↔GPU | RDMA, requires rendezvous |
| `torchrun --nproc-per-node=8 --nnodes=2 ... --mode alltoall` | Cross-server all-to-all | 16-rank, top-6 dispatch |

## Procedure

### 1. PCIe staging baseline (single GPU)

This measures the host-memory staging ceiling — critical because RTX 5090 lacks GPUDirect RDMA so every cross-server GPU transfer needs two PCIe passes (D2H → network → H2D).

```bash
cd /path/to/nccl/rdma
# Default tokens: 1,8,64,128,512,8192
# Default payload: top-6 expert dispatch (7168*2*6 = 86016 bytes/token)
python3 forward_comm_benchmark.py --mode pcie --output-json pcie_gpu6_activation.json
```

Results include H2D and D2H `steady_payload_GBps` and `sync_latency_p50_us` per token count. At 8192 tokens (672 MiB), steady H2D ~56 GB/s, D2H ~57 GB/s on RTX 5090.

### 2. Local GPU-to-GPU P2P

Two physical GPUs on the same host, staged PCIe path (no NVLink, no CUDA P2P for RTX 5090).

```bash
torchrun --nproc-per-node=2 forward_comm_benchmark.py --mode p2p \
  --output-json local_p2p_gpu6_gpu7_activation_corrected.json
```

At 8192 tokens (112 MiB), p50 latency ~4.47 ms, steady ~26.59 GB/s.

### 3. Cross-server GPU-to-GPU P2P

Requires matching NCCL runtime on both hosts and RoCE RDMA connectivity.

**On both hosts**, launch with identical arguments and rendezvous:

```bash
# Host A (oem88, RDMA=10.10.68.88): master
torchrun \
  --nproc-per-node=8 \
  --nnodes=2 \
  --node-rank=0 \
  --master-addr=10.10.68.88 \
  --master-port=29500 \
  forward_comm_benchmark.py --mode p2p \
  --output-json cross_server_p2p_gpu6_gpu6_activation_rdma_corrected.json

# Host B (oem96, RDMA=10.10.68.96): worker
torchrun \
  --nproc-per-node=8 \
  --nnodes=2 \
  --node-rank=1 \
  --master-addr=10.10.68.88 \
  --master-port=29500 \
  forward_comm_benchmark.py --mode p2p \
  --output-json cross_server_p2p_gpu6_gpu6_activation_rdma_corrected.json
```

The rendezvous uses management IPs (`10.10.68.x`); data-plane traffic flows over RoCE (`10.10.68.x`). At 8192 tokens (112 MiB), p50 latency ~10.66 ms, steady ~11.05 GB/s on a 100-Gbit RoCE link.

### 4. Local 8-GPU all-to-all (top-6 expert dispatch)

Simulates expert-parallel MoE routing within one host:

```bash
torchrun --nproc-per-node=8 forward_comm_benchmark.py --mode alltoall \
  --output-json local_alltoall_8gpu_ep_top6_corrected.json
```

At 8192 tokens (672 MiB/rank), p50 latency ~27.08 ms, steady ~21 GB/s bidirectional.

### 5. Cross-server 16-GPU all-to-all

Run with `--nnodes=2 --node-rank=0/1`:

```bash
# Host A (master)
torchrun \
  --nproc-per-node=8 --nnodes=2 --node-rank=0 \
  --master-addr=10.10.68.88 --master-port=29500 \
  forward_comm_benchmark.py --mode alltoall \
  --output-json cross_server_alltoall_16gpu_ep_top6_rdma_corrected.json
```

At 8192 tokens (672 MiB/rank), p50 latency ~264 ms, steady ~21.34 GB/s cross-server bidirectional. Half the payload goes to the other host; the rest stays local.

### 6. Tune `NCCL_IB_QPS_PER_CONNECTION`

Set the env var before `torchrun`:

```bash
NCCL_IB_QPS_PER_CONNECTION=1 torchrun ... --mode alltoall ...
```

Key finding: at **512 tokens** with QPS=4, latency degrades to ~75-96 ms (cliff). With QPS=1, it drops to **16.85 ms** (~20.9 GB/s). At 8192 tokens, QPS setting has negligible effect. Default `4` is not optimal for this topology.

### 7. Build NCCL with RoCE MTU receiver patch (temporary)

When RDMA peers advertise mismatched MTU, original NCCL fails on the first GPU buffer with QP errors. Apply the receiver-side MTU cap patch:

```bash
git clone --depth 1 --branch v2.28.9-1 https://github.com/NVIDIA/nccl.git /tmp/nccl-v2.28.9
git -C /tmp/nccl-v2.28.9 apply \
  /path/to/nccl_2.28.9_roce_receiver_mtu.patch
make -C /tmp/nccl-v2.28.9 -j32 src.build \
  CUDA_HOME=/usr/local/cuda \
  NVCC_GENCODE='-gencode=arch=compute_120,code=sm_120'
```

Load via `LD_PRELOAD` on both sides with the exact same `.so` file. This patch is diagnostic only — the permanent fix is to unify RoCE MTU across the fabric.

## Pitfalls

- **RTX 5090 has no GPUDirect RDMA.** CUDA reports `GPU_DIRECT_RDMA_SUPPORTED=0`. All cross-server GPU transfers go through host-memory staging (D2H → RoCE → H2D). Results on GDR-capable GPUs (RTX PRO 6000) will differ.
- **MTU mismatch silently breaks NCCL** while `ib_write_bw` still works (perftest negotiates a common MTU; NCCL does not). Check MTU with `ibv_devinfo -d <hca> | grep active_mtu` on both peers. Symptom: `local access violation work queue error` on the smaller-MTU side.
- **NCCL version mismatch causes bootstrap failure.** Matching SHA-256 of `libnccl.so` is required. `torch.cuda.nccl.version()` may report a version that differs from the runtime-loaded library. Verify with `cat /proc/<pid>/maps | grep nccl`.
- **`NCCL_IB_QPS_PER_CONNECTION=4` can cause 512-token performance cliffs.** The optimal value depends on HCA count, rank count, and payload size. Always A/B test `1` vs `4` in real vLLM before committing.
- **Cross-server results include both PCIe staging and network.** The `nnodes=2` all-to-all compares world size 16 (local 8 + remote 8) against local world size 8 — this measures the real EP scaling cost, not a pure network microbenchmark.
- **all-to-all uses uniform split.** Real MoE dispatch has expert token imbalance and metadata overhead not captured here.
- **The NCCL MTU patch is a temporary workaround.** Do not use it as a permanent replacement for fixing the fabric MTU.

## Verification

A successful PCIe baseline should show steady H2D throughput of ~56 GB/s and D2H ~57 GB/s at 8192 tokens (672 MiB payload). A successful P2P cross-server test should complete all iterations without NCCL errors and the output JSON should contain `sync_latency_p50_us` and `steady_payload_GBps` for each token count, with validation flag implicitly true (the script validates received data before recording).
