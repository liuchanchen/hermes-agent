# Ascend 950 Deployment: Super Nodes & Clusters

## Variant Selection Guide

### Use 950PR When:

- **Recommendation systems**: High throughput inference, large embedding tables fit in 128GB HBM
- **LLM Prefill**: Input processing phase where bandwidth is the bottleneck, compute-bound
- **Multi-modal inference**: Image/video understanding, moderate KV Cache needs
- **Cost-sensitive deployments**: Lower HBM cost than 950DT

### Use 950DT When:

- **LLM Pretraining**: 4 TB/s bandwidth critical for gradient accumulation and optimizer states
- **LLM Post-training (RLHF/DPO)**: Full model + reference model + optimizer states need 144GB
- **Long-context inference**: Large KV Cache requires 144GB capacity
- **Decode-heavy workloads**: Autoregressive generation is memory-bandwidth bound

## Memory Planning

### LLM Training Memory Budget (per 950DT card)

```
Total HBM: 144 GB

Model Parameters (FP32 master):      ~4N GB        (N = billions of params)
  Example 70B model:                  ~280 GB       (>1 card needed)
Optimizer States (Adam):             ~8N GB
  Example 70B model:                  ~560 GB
Gradients (FP32):                    ~4N GB
Activations (with recompute):        variable
```

### LLM Inference Memory Budget (per card)

```
Total HBM: 128 GB (950PR) or 144 GB (950DT)

Model Weights (FP8/HiF8):            ~N GB         (N = billions)
  Example 70B FP8:                   ~70 GB
KV Cache (per token, per layer):
  2 × num_layers × num_kv_heads × head_dim × 2 bytes (FP16)
  Example Llama 70B (80 layers, 8 KV heads, 128 dim):
    Per token: 2 × 80 × 8 × 128 × 2 = 327,680 bytes ≈ 320 KB
    128K context: 320 KB × 128K = 40 GB

Remaining for weights + overhead:    capacity - KV Cache
  950PR 128GB: 128 - 40 = 88 GB for weights
  950DT 144GB: 144 - 40 = 104 GB for weights
```

## Cluster Sizing

### Training Cluster Estimate

For a 1T parameter model with Adam optimizer:

```
Model params (FP32):     4 TB
Optimizer states:         8 TB
Gradients:                4 TB
─────────────────────────────
Total:                   16 TB

Per 950DT card: 144 GB HBM
Cards needed (DP=1):     16 TB / 144 GB ≈ 114 cards
With TP=8, PP=4:         114 × 32 ≈ 3648 cards
```

### Super Node Topology Options

| Scale | Topology | UB Ports/Card | Notes |
|-------|----------|---------------|-------|
| 8 cards | Full Mesh | 7 | Direct, no switch |
| 64 cards | 2-tier Clos | 16 | 1:1 oversubscription |
| 512 cards | 3-tier Clos | 16 | Requires UB Switches |
| 8192 cards | Multi-tier Clos | 16+ | Full super node |

## Precision Strategy

### Training

```
Forward pass:  HiF8 or MXFP8 for matmuls → highest throughput
               BF16 for sensitive ops (softmax, norm)
Backward pass: HiF8 for gradients (wider dynamic range than FP8 E4M3)
               FP32 for weight update (master weights)
```

### Inference

```
Prefill (compute-bound):  MXFP4 for attention matmuls
                          FP8 for MLP
Decode (memory-bound):    HiF8 or MXFP8 KV Cache
                          FP8 weights
```

### Recommended Format Mapping

| Operation | Training | Inference |
|-----------|----------|-----------|
| Q/K/V projection | HiF8 | MXFP8 |
| Attention scores | BF16 | MXFP4 |
| Output projection | HiF8 | FP8 |
| MLP (up/gate) | HiF8 | MXFP8 |
| MLP (down) | HiF8 | FP8 |
| LayerNorm/RMSNorm | FP32 | FP16 |
| Softmax | FP32 | FP16 |
| KV Cache store | — | MXFP8/HiF8 |

## Communication Patterns

### Data Parallel (DP)
```
AllReduce gradients across all DP replicas
→ Use CCU hardware offload for AllReduce
→ RTP transport for reliability
```

### Tensor Parallel (TP)
```
AllReduce/AllGather activations per layer
→ Intra-node: UB Memory (lowest latency)
→ Inter-node: URMA (async RDMA)
```

### Pipeline Parallel (PP)
```
Point-to-point activation/gradient passing
→ URMA Send/Receive between pipeline stages
```

### Expert Parallel (EP, for MoE)
```
All2All token dispatch and combine
→ Use CCU hardware All2All/All2Allv
→ CTP transport for throughput (loss-tolerant)
```

## Software Deployment

### CANN Version Requirements

- Minimum CANN version for Ascend 950: Check Huawei compatibility matrix
- PyTorch adapter: `torch_npu` plugin
- vLLM: Community support may vary — check for Ascend backend

### Typical Stack

```
PyTorch / MindSpore
    ↓
torch_npu / mindspore adapter
    ↓
CANN (Ascend C, GE, Runtime)
    ↓
Firmware / Driver
    ↓
Ascend 950 Hardware
```

## Performance Estimation

### Peak Throughput (BF16 Training, 950DT)

```
Theoretical peak: 547 TFLOPS BF16

Realistic utilization:
  - GEMM-heavy workloads: 50-60% → 273-328 TFLOPS
  - Attention-heavy: 40-50% (bandwidth-bound)
  - Communication overhead: -5-15% (depending on topology)
```

### Memory Bandwidth (Decode, 950DT)

```
Theoretical: 4 TB/s

Realistic:
  - Decode phase (memory-bound): 70-85% of bandwidth utilized
  - Small batch: lower utilization (latency-bound)
  - Large batch: higher utilization (throughput-bound)
```

## Monitoring & Profiling

- **STARS TOP-DOWN profiling**: Real-time task timelines, compute/bandwidth/power per task
- **CANN Profiling Tools**: Operator-level profiling, memory usage, communication traces
- **Cluster monitoring**: UB link utilization, CCU throughput, error rates

## Common Deployment Pitfalls

1. **Wrong variant for workload**: Using 950PR for training → 1.6 TB/s insufficient
2. **Ignoring UBoE port sharing**: Enabling 2×400G UBoE reduces UB ports from 18→16
3. **Precision mismatch**: Using FP16 when MXFP8/HiF8 gives 2× throughput
4. **Not using CCU**: Software collectives waste AI Core time and bus bandwidth
5. **No STARS Group scheduling**: Cross-die L2 access increases latency without die-affine scheduling
6. **KV Cache overflow**: Underestimating KV Cache size for long-context inference
