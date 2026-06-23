---
name: ascend-950
description: Use when working with Huawei Ascend 950 series NPU — architecture specs, DaVinci Core programming, CANN software stack, UB interconnect, super node deployment, and performance optimization. Covers 950PR (128GB/1.6TBps) and 950DT (144GB/4TBps) variants.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [ascend, huawei, npu, davinci, cann, ai-accelerator, hbm, ub-interconnect, super-node, llm-training, llm-inference]
    related_skills: [serving-llms-vllm, model-deployment]
---

# Ascend 950 NPU Architecture

Complete reference for Huawei Ascend 950 series NPU — 3rd generation DaVinci architecture for AI training and inference at scale.

## Overview

The Ascend 950 series is Huawei's flagship AI computing chip built on the 3rd-generation DaVinci architecture. Two variants target different workloads:

| Variant | HBM | Bandwidth | Target |
|---------|-----|-----------|--------|
| **950PR** | 128 GB | 1.6 TB/s | Recommendations, LLM Prefill, multi-modal inference |
| **950DT** | 144 GB | 4 TB/s | Full LLM lifecycle: pretraining, post-training, inference (Decode+Prefill) |

**Chiplet design**: 2× AI Die + 2× IO Die + 4–8 HBM stacks, connected via D2D Clink. Full UMA (Unified Memory Access) across all dies.

## Quick Reference

### Compute (950DT max config)

| Precision | TFLOPS/TOPS |
|-----------|-------------|
| MXFP4 | 2007 |
| HiF8 / MXFP8 / FP8 | 1034 |
| BF16 / FP16 | 547 |
| TF32 | 273 |
| FP32 (Vector only) | 30 |
| INT8 | 1034 |

### AI Subsystem

- **36 AI Cores** (1 Cube + 2 Vector each)
- Cube Core: matrix/tensor operations with MXFP4/8, HiF8, FP8, BF16, FP16, TF32, INT8
- Vector Core: 2× FP32/FP16 over previous gen, SIMD/SIMT hybrid
- 128MB L2 Cache (UMA, 512B cache line, 128B Sector)

### CPU & Media

- **8× Linx816** ARMv8-A cores (dual-threaded, 4 clusters)
- **DVPP**: 4× VPC, 4× JPEGE, 8× JPEGD (max 32K×32K)

### Interconnect

| Interface | Bandwidth | Notes |
|-----------|-----------|-------|
| UB 2.0 (Unified Bus) | 2016 GB/s bidirectional | 18× x4 Ports, 112Gbps SerDes |
| UBoE | 2× 400 Gbps | UB over Ethernet |
| PCIe 5.0 | 128 GB/s bidirectional | x16, EP/RC dual-mode |

### Scale

- **Super Node**: up to 8192 cards
- **Max Cluster**: 128K+ cards
- **Topologies**: nD-Mesh, Clos, Full Mesh+Clos hybrid

## When to Use

- Designing or deploying workloads on Ascend 950 hardware
- Estimating model performance (TFLOPS, memory, bandwidth) on Ascend 950
- Programming with CANN / Ascend C for DaVinci Core
- Configuring UB interconnect and super node topologies
- Comparing Ascend 950 against other AI accelerators (e.g., NVIDIA H100/B200)
- Planning LLM training/inference deployments at scale

## Detailed References

See linked reference files:

- `references/specifications.md` — Complete spec tables for 950PR and 950DT
- `references/architecture.md` — Deep dive: DaVinci Core, Memory hierarchy, STARS 2.0
- `references/programming-model.md` — Cube/Vector programming, HiF8, SIMD/SIMT, NDDMA
- `references/interconnect.md` — UB 2.0, URMA, UB Memory, CCU, UBoE, super nodes
- `references/deployment.md` — Cluster topologies, super node scale-out, memory pool

## Key Innovations

1. **HiF8 format**: 38 exponent values (vs FP8 E4M3's 18), tapered precision — no scale factor needed, near-FP16 dynamic range
2. **SIMD/SIMT hybrid**: SIMD for regular element-wise (high throughput), SIMT for irregular gather/scatter (flexibility)
3. **NDDMA**: 5D data rearrangement in hardware, automatic cache-friendly 128B reads
4. **CCU**: Hardware collective communication offload — Broadcast, ReduceScatter, AllGather, AllReduce, All2All
5. **STARS 2.0**: 2048 task streams, ns-level HSCB scheduling, 16-way resource partitioning
6. **Sector Cache**: 128B granularity within 512B cache lines, CMO for prefetch/writeback/invalidate/flush

## Software Stack

- **CANN**: Compute Architecture for Neural Networks — full heterogeneous computing stack
- **Ascend C**: Kernel-level programming language for DaVinci Core
- Layers: Acceleration libraries → Operator programming → Compiler → Runtime
- Fully open-source and open to developers

## Common Pitfalls

1. **Confusing 950PR vs 950DT memory**: 950PR has 128GB but only 1.6TB/s — insufficient for full training. Use 950DT (144GB/4TB/s) for training workloads.
2. **Assuming FP16 is the primary precision**: Ascend 950 is designed for MXFP4/MXFP8/HiF8 as primary formats. FP16/BF16 peak is only 547 TFLOPS vs 2007 MXFP4.
3. **Ignoring UB port multiplexing**: UBoE and UB share SerDes ports. Using 2×400G UBoE reduces UB Link ports by 2.
4. **L2 Cache locality**: Cross-die L2 access has higher latency. Use STARS Group scheduling for die-affine task placement.
5. **SIMT as primary path**: SIMT is auxiliary — SIMD is the main compute path. Most vector workloads should use SIMD.
6. **Overlooking CCU**: Don't implement collectives in software when CCU can hardware-offload AllReduce/AllGather/etc.

## Verification Checklist

- [ ] Correct variant selected (PR vs DT) for target workload
- [ ] Precision format matches model requirements (MXFP4/8, HiF8, FP8, BF16)
- [ ] Memory capacity/bandwidth sufficient for model + KV Cache
- [ ] UB topology configured for target cluster scale
- [ ] CANN version compatible with Ascend 950
- [ ] CCU enabled for collective communication offload
