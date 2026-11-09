# PP=2 Across 2 Nodes in ds4-sm120 Branch

**Updated: 2026-05-26 — PP=2 IS confirmed working across 2 nodes**

## The Proven Configuration

The existing script at `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` on 70.96 successfully runs TP=8+PP=2+EP=8 across 70.96 (master) and 70.98 (worker).

## Critical Env Vars Required (the key difference)

Unlike DP mode where VLLM_HOST_IP is optional, **PP=2 across nodes REQUIRES** `VLLM_HOST_IP`:

```bash
# Master (70.96):
export VLLM_HOST_IP="10.10.71.96"

# Worker (70.98):
export VLLM_HOST_IP="10.10.71.98"
```

Without this, the multiproc executor's `get_distributed_init_method` uses `get_loopback_ip()` which returns `127.0.0.1`. Each node then initializes its own local `world_size=16` with `tcp://127.0.0.1:random_port`, crashing with:

```
AssertionError: DP adjusted local rank 13 is out of bounds.
```

## Full NCCL RoCE v2 Config

```
export NCCL_SOCKET_IFNAME=ens35f0np0
export GLOO_SOCKET_IFNAME=ens35f0np0
export TP_SOCKET_IFNAME=ens35f0np0
export NCCL_IB_DISABLE=0
export NCCL_IB_HCA=mlx5_0
export NCCL_IB_GID_INDEX=3
export NCCL_IB_TIMEOUT=23
export NCCL_IB_QPS_PER_CONNECTION=4
export NCCL_IB_TC=136
export NCCL_CROSS_NIC=0
export NCCL_ALGO=Ring
export NCCL_MIN_NCHANNELS=8
export NCCL_NET=IB
```

## Required CLI Flags

Both master and worker need:
- `--nnodes 2 --node-rank <0|1>` — tells vLLM to expect 2 nodes
- `--master-addr 10.10.71.96 --master-port 29505` — cross-node TCPStore
- `--pipeline-parallel-size 2` — enables PP (NO `--data-parallel-*` flags)

Worker additionally needs: `--headless`

## Performance Summary

PP=2 vs DP=2 on the same 2-node cluster (8192/512 config):

| Metric | DP | PP | PP Advantage |
|--------|---|---|-------------|
| S1 TTFT | 3.3s | **2.2s** | 35% faster |
| S1 TPOT | 58.7ms | 99.7ms | DP 41% faster (PP decode overhead) |
| S1 throughput | 118 tok/s | 86 tok/s | DP 27% more |
| S2 60K TTFT | 243.9s | **186.7s** | 23% faster |
| S3 prefix TTFT | 141.9s | **44.4s** | **69% faster** |
| S3 throughput | 4.12 tok/s | **7.15 tok/s** | 74% more |
