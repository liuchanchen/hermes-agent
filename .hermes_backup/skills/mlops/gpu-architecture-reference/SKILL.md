---
name: gpu-architecture-reference
description: Reference knowledge base on GPU/NPU hardware architecture — Huawei Ascend 950 NPU and Super Node/ Super Pod scale-up infrastructure, scale-out protocols, and interconnect topology
version: 1.0.0
author: curator
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Hardware, GPU, NPU, Ascend, Super-Node, Interconnect, Architecture]
---

# GPU & NPU Architecture Reference

Knowledge base for AI-scale hardware architecture. Covers Huawei Ascend 950 NPU series specifications and Super Node/Super Pod scale-up infrastructure protocols.

## When to use

- You need Ascend 950 NPU specs (950PR vs 950DT variants, compute specs, memory bandwidth)
- You need to understand Super Node / Super Pod scale-up vs scale-out topology
- You need a comparison of interconnect protocols (NVLink, GLink, UB 2.0, UALink, ETH-X, OISA)
- You're designing or evaluating AI training/inference clusters

## 1. Ascend 950 NPU (Huawei)

Huawei's 3rd-generation DaVinci NPU architecture.

### Variants

| Variant | Memory | Bandwidth | Primary Use |
|---------|--------|-----------|-------------|
| **950PR** | 128 GB HBM3 | 1.6 TBps | Inference, prefill-heavy |
| **950DT** | 144 GB HBM3 | 4 TBps | Full training |

### Compute

| Precision | 950PR TFLOPS | 950DT TFLOPS |
|-----------|-------------|-------------|
| MXFP4 | 2007 | 2007 |
| BF16/FP16 | 547 | 547 |

### Architecture highlights
- **AI Subsystem**: 36 AI Cores per NPU
- **Interconnect (UB 2.0 / 灵衢)**: 2016 GB/s bidirectional per direction, open protocol
- **HiF8 format**: Huawei's native 8-bit floating-point
- **SIMD/SIMT hybrid**: CUBE (matrix) unit + VECTOR (vector) unit
- **NDDMA**: Neural-network-specific DMA engine
- **CCU**: Hardware collective communications unit
- **STARS 2.0**: Scheduling system for AI training

### Software stack
- CANN (Compute Architecture for Neural Networks)
- Ascend C programming language

### Super Node scaling
- 8192 cards in one super node
- 128,000+ cluster via multi-level interconnect

## 2. Super Node / Super Pod

Scale-up infrastructure based on H3C white paper.

### Definition
Rack-as-computer architecture where GPUs/NPUs share unified memory semantic (load-store model, not message-passing).

### Scale-up vs Scale-out

| Property | Scale-up (Super Node) | Scale-out (Ethernet) |
|----------|----------------------|---------------------|
| Memory model | Unified (load/store) | Distributed (send/receive) |
| Latency | 100s ns–1µs | 1–10 µs |
| Bandwidth | TB/s | GB/s |
| Topology | Fully connected | Tree/fat-tree |
| Protocol | NVLink, UB 2.0 | InfiniBand, RoCE |

### Protocol comparison

| Protocol | Bandwidth | Topology | Max Scale | Ecosystem |
|----------|-----------|----------|-----------|-----------|
| NVLink 5.0 | 1.8 TB/s (18×200GB) | NVL72 | 72 GPUs | NVIDIA |
| NVLink 6.0 | 4.6 TB/s | NVL144 | 144 GPUs | NVIDIA (next gen) |
| UB 2.0 (灵衢) | 2016 GB/s | DaVinci Core | 8K cards | Huawei |
| GLink | 900 GB/s | GPU mesh | 160+ | Huawei |
| UALink | ~900 GB/s | Switch fabric | 8–256 | AMD/Intel/Google (open) |
| ETH-X | 1024 Gbps/8-lane | Switch fabric | 512 GPUs | Open |
| OISA 2.0 | Up to 400 GB/s | Optical | Unlimited | Open |
| SUE | 200 GB/s | PCIe 6.0 | Scale-down | Ideal for small clusters |

### Hardware design
- Single rack: 120 kW power, liquid cooling required
- Rack weight: ~1.8 tons → 16 kN/m² floor load minimum
- Architecture: Rack-level NVSwitch or disaggregated chassis design

### Deployment requirements
- Liquid cooling
- 3-phase power at rack
- Reinforced flooring
- Optical interconnect for cross-rack

## Pitfalls

- **UB 2.0 vs UALink**: UB 2.0 is Huawei proprietary; UALink is an open standard by AMD/Intel/Google consortium. They are NOT compatible.
- **NVL72 = 130 TB/s**: This is aggregate bisection, not per-GPU bandwidth. Per-GPU NVLink is 900 GB/s bidirectional.
- **Scale-up ≠ scale-out**: These solve different problems. Super Node is for model-parallel training; Ethernet for data-parallel.
- **Protocol licensing**: Only UALink, OISA, and ETH-X are open standards. NVLink requires NVIDIA hardware, UB 2.0 requires Huawei hardware.
