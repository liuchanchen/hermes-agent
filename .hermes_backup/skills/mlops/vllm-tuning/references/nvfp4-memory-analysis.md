# NVFP4 Memory Budget Analysis: Qwen3.6-35B-A3B-NVFP4

## Model Architecture

- **Architecture**: Qwen3.6-35B-A3B (qwen3_5_moe) — MoE with 256 experts, 8 active
- **Hidden size**: 2048, **MoE intermediate size**: 512, **Layers**: 40
- **Total MoE params**: ~32.2B (256 experts × 40 layers × 3 × 2048 × 512)
- **Attention params**: ~1.3B (FP8)
- **Disk size**: 22GB (NVFP4 checkpoint)

## Why 22GB on Disk → 30.4 GiB/GPU with TP=2

### On-Disk Storage (NVFP4 compressed)

NVFP4 (W4A16) stores weights at 4 bits per parameter, but with scale overhead:

| Component | Size | Calculation |
|-----------|------|-------------|
| MoE weights (uint8, 2 FP4 packed/byte) | ~16.1 GB | 32.2B params × 0.5 bytes/param |
| MoE block scales (fp8_e4m3, group_size=16) | ~2.0 GB | 32.2B params / 16 × 1 byte |
| MoE global scales (fp32 per-tensor) | negligible | |
| Attention weights (FP8) | ~1.3 GB | 1.3B params × 1 byte |
| Other (embeddings, norms, etc.) | ~2.6 GB | |
| **Total on disk** | **~22 GB** | |

Effective storage per MoE param: 0.5 + 0.0625 = **0.5625 bytes/param** (not 0.5)

### In-GPU Memory with TP=2 (RTX 5090, 31.36 GiB usable)

| Component | Per GPU | Notes |
|-----------|---------|-------|
| NVFP4 weights (sharded) | ~11.4 GB | Half of 22GB total |
| Activation workspace (bf16) | ~6-8 GB | vLLM allocates bf16 buffers for dequantized activations during forward pass |
| CUDA graph capture | ~3-5 GB | FULL_AND_PIECEWISE cudagraph mode |
| KV cache reservation | ~4-6 GB | Pre-allocated based on gpu_memory_utilization × remaining |
| Framework overhead | ~2-3 GB | PyTorch CUDA context, NCCL buffers, etc. |
| **Total** | **~30.4 GB** | Exceeds 31.36 GiB → OOM on last 256 MiB allocation |

### Root Cause

vLLM's NVFP4 implementation stores weights compressed (uint8 + fp8 scales) but must allocate **bf16 activation workspace** for the dequantized intermediate results during computation. With TP=2 on 32GB cards:

- Weights alone: ~11.4 GiB/GPU (fits)
- But workspace + CUDA graphs + KV cache reservation pushes total to 30.4 GiB
- The final 256 MiB allocation fails because only ~164 MiB free remains
- Reducing `--max-model-len` to 32768 does NOT help because the model weights + workspace already consume 30+ GiB

### Solutions

| TP | GPUs | Weights/GPU | Total Est. | Fits 32GB? | Fits 96GB? |
|----|------|-------------|------------|------------|------------|
| TP=2 | 2 | ~11.4 GB | ~30.4 GB | ❌ OOM | ✅ |
| TP=4 | 4 | ~5.7 GB | ~15 GB | ✅ | ✅ |
| TP=1 | 1 | ~22 GB | ~30+ GB | ❌ OOM | ✅ |

**Minimum for RTX 5090 (32GB)**: TP=4 with 4 GPUs
**Minimum for RTX PRO 6000 (96GB)**: TP=1 should work

### Key Takeaway

NVFP4's compression ratio for MoE models is only ~5.6x vs bf16 (not 8x) due to fp8 block scales + fp32 global scales overhead. The real GPU memory budget is dominated by activation workspace and CUDA graph allocations, not just weights. Always calculate total GPU budget (weights + workspace + CUDA graphs + KV cache), not just checkpoint size.
