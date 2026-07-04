# Cross-Node NCCL Bandwidth Testing (70.96 + 70.98)

## Problem

nccl-tests `all_reduce_perf` does NOT support multi-node out of the box. Running `./build/all_reduce_perf -g 8` on two nodes separately creates **two independent 8-rank communicators** — NOT a 16-rank cross-node communicator. Both nodes appear to complete successfully but each only tests its local NVLink/PCIe bandwidth.

## Approach

### Option A: PyTorch distributed (simplest)

Write a small Python script using `torch.distributed` with NCCL backend, launch on both nodes simultaneously:

```python
# cross_nccl_test.py
import os, time, torch, torch.distributed as dist
RANK = int(os.environ.get("RANK", "0"))
WORLD_SIZE = int(os.environ.get("WORLD_SIZE", "16"))
MASTER_ADDR = os.environ.get("MASTER_ADDR", "192.168.66.10")
MASTER_PORT = int(os.environ.get("MASTER_PORT", "29500"))
LOCAL_GPU = RANK % 8
torch.cuda.set_device(LOCAL_GPU)
dist.init_process_group("nccl", init_method=f"tcp://{MASTER_ADDR}:{MASTER_PORT}",
    world_size=WORLD_SIZE, rank=RANK)
# Benchmark loop with all_reduce + timing
dist.destroy_process_group()
```

Launch on node 2 (worker) in background:
```bash
ssh jianliu@10.10.70.98 "nohup bash -c '
  export NCCL_SOCKET_IFNAME=bond0 NCCL_NET=IB NCCL_IB_HCA=mlx5_bond_0
  export NCCL_IB_GID_INDEX=3 NCCL_IB_TIMEOUT=23 NCCL_IB_QPS_PER_CONNECTION=4
  export NCCL_IB_TC=136 NCCL_CROSS_NIC=0
  RANK=8 WORLD_SIZE=16 MASTER_ADDR=192.168.66.10 MASTER_PORT=29500
  exec /data/venvs/vllm-ds4/bin/python3 /tmp/cross_nccl_test.py
' > /tmp/nccl_cross_98.log 2>&1 &"
sleep 3
# Launch on node 1 (master)
cd /tmp
RANK=0 WORLD_SIZE=16 MASTER_ADDR=192.168.66.10 MASTER_PORT=29500 \
  /data/venvs/vllm-ds4/bin/python3 /tmp/cross_nccl_test.py
```

### Option B: MPI + nccl-tests

Install OpenMPI on both nodes, then:
```bash
mpirun -host 192.168.66.10:8,192.168.66.20:8 \
  -env NCCL_SOCKET_IFNAME bond0 \
  -env NCCL_NET IB \
  -env NCCL_IB_HCA mlx5_bond_0 \
  /home/jianliu/work/bandwidth_test/nccl-tests/build/all_reduce_perf \
  -b 256M -e 4G -f 2 -g 16 -n 20 -w 5
```

## Prerequisites

1. **Passwordless SSH keys in both directions** between all nodes — MPI and PyTorch distributed init both use SSH for bootstrap
2. **Matching nccl-tests binary** on all nodes — copy via SSH pipe:
   ```bash
   tar czf /tmp/nccl-tests.tar.gz -C ~/work/bandwidth_test nccl-tests
   cat /tmp/nccl-tests.tar.gz | ssh node2 'cat > /tmp/nccl-tests.tar.gz'
   ssh node2 'cd ~/work/bandwidth_test && tar xzf /tmp/nccl-tests.tar.gz'
   ```
3. **RDMA reachability** — `ping -c1 192.168.66.20` from 96, and vice versa
4. **All GPUs free** — check with `nvidia-smi`, kill any orphaned vLLM/VLLM processes

## Known Results (Single-Node)

| Node | Avg BusBW | Peak BusBW | Notes |
|------|:---------:|:----------:|-------|
| 70.96 | 14.5 GB/s | 33.7 GB/s | RTX PRO 6000, 2 NUMA domains |
| 70.98 | 15.4 GB/s | 38.8 GB/s | RTX PRO 6000, slightly higher (NUMA diff?) |

Cross-node bandwidth between 70.96 and 70.98 over RoCE v2 (100GbE, bond0, 192.168.66.x) has NOT been successfully measured yet — the PyTorch approach had a `dist.init_process_group` hang that needs to be resolved.

## Pitfalls

- **nccl-tests runs independently** — without MPI or a launcher, each node only tests its local GPUs
- **No SSH key on worker** — 70.98 may be missing `~/.ssh/id_ed25519` (only had `authorized_keys`). Generate with `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ''`
- **RDMA device name needs auto-detection** — both nodes currently show `mlx5_bond_0`, but this may change with kernel/driver updates. Always run `rdma link show` to confirm
- **dist.init_process_group can hang** — if MASTER_ADDR:MASTER_PORT is unreachable from the worker, init blocks indefinitely. Use `NCCL_DEBUG=INFO` to diagnose
- **NCCL 2.30.4 confirmed working** on both nodes for single-node. For cross-node, ensure NCCL_NET=IB and NCCL_IB_HCA match the local RDMA device
