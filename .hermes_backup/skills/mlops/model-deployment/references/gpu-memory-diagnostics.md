# Multi-Node vLLM DP Cluster — GPU Memory Diagnostics

## The Mixed-GPU Problem

The 70.96 + 70.98 cluster has asymmetric GPU memory:
- **70.96**: 8× RTX 5090 **32 GB** each → 8 × 32 = 256 GB total
- **70.98**: 8× RTX PRO 6000 **96 GB** each → 8 × 96 = 768 GB total

In multi-node DP mode, each node loads the **full model** independently. For DeepSeek-V4-Pro:

| Component | Size (per node) |
|-----------|----------------|
| Dense weights (FP8) | ~2.6 GB/GPU × 8 = 21 GB |
| Shared experts (FP4) | ~0.5 GB/GPU × 8 = 4 GB |
| Routed experts (FP4, 1/16) | ~52 GB |
| Embedding | ~0.5 GB |
| **Total model** | **~77–90 GB** (varies by TP sharding) |

On a 96 GB/node (70.98): 96 - 90 = **~6 GB free** for KV cache
On a 32 GB/node (70.96): Need TP=8 across all 8 GPUs = 8 × 32 = 256 GB, but each GPU only carries 1/8 of weights ≈ ~11 GB/GPU, leaving ~21 GB/GPU for KV cache

Wait — in DP, each node has its OWN 8 GPUs running TP=8. So:
- 70.98: 96 GB/GPU, model loads ~11 GB/GPU of weights → ~85 GB/GPU free for KV cache
- 70.96: 32 GB/GPU, model loads ~11 GB/GPU of weights → ~21 GB/GPU free for KV cache

**But** the error shows `5.53 GiB available KV cache` on 70.98. This means the model is taking ~90+ GB on 70.98. Why?

## Root Cause: Mixed GPU Hardware Failure is Misleading

The "5.53 GiB available" error on 70.98 actually comes from **the EngineCore only seeing ONE GPU** (rank 0 within TP group). In this vLLM version, DP EngineCore on each node does its own KVCache profiling independently. The failure shows the per-GPU memory left after loading the sharded weights.

**Fix applied**: `max-num-batched-tokens=16384` reduces the per-GPU profiling burden. `max-num-seqs=256` reduces CUDA graph capture overhead. The 96 GB GPUs can handle this configuration.

## Diagnostic Commands

```bash
# Check memory on all GPUs
nvidia-smi --query-gpu=index,memory.total,memory.used,memory.free --format=csv,noheader

# Check which processes are using GPU memory
nvidia-smi | grep "Processes" -A 20

# After vLLM crash: check for leftover VLLM processes
nvidia-smi | grep VLLM

# Kill all VLLM processes on a node
ps aux | grep vllm | grep -v grep | awk '{print $2}' | xargs kill -9

# Calculate how much KV cache a model len requires
# Formula for FP8 KV cache per GPU (TP=8):
#   seq_len × hidden_size × layers × kv_heads × 2 (k+v) × 1 (fp8) ÷ TP
# For DeepSeek-V4 with 1048576 seq:
kv_cache_gb = 1048576 * 7168 * 60 * 1 * 2 * 1 / 8 / 1024**3
print(f"{kv_cache_gb:.1f} GiB")  # ~24 GiB
```
