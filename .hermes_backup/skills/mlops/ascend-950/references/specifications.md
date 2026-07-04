# Ascend 950 Complete Specifications

## Chip Variants

| Spec | 950PR (3 configs) | 950DT (3 configs) |
|------|-------------------|-------------------|
| **AI Cores** | 32/28 Cube, 64/56 Vector | 36/32/28 Cube, 72/64/56 Vector |

## Compute Performance

### Combined (Cube + Vector) TFLOPS/TOPS

| Precision | 950PR Max | 950PR Mid | 950PR Min | 950DT Max | 950DT Mid | 950DT Min |
|-----------|-----------|-----------|-----------|-----------|-----------|-----------|
| **MXFP4** | 1784 | 1561 | — | 2007 | 1784 | 1561 |
| **HiF8/MXFP8/FP8** | 919 | 804 | — | 1034 | 919 | 804 |
| **INT8** | 919 | 804 | — | 1034 | 919 | 804 |
| **BF16/FP16** | 486 | 425 | — | 547 | 486 | 425 |
| **TF32** | 243 | 212 | — | 273 | 243 | 212 |

### Cube Core Only

| Precision | 950PR Max | 950PR Mid | 950DT Max | 950DT Mid | 950DT Min |
|-----------|-----------|-----------|-----------|-----------|-----------|
| **MXFP4** | 1730 | 1513 | 1946 | 1730 | 1513 |
| **HiF8/MXFP8/FP8** | 865 | 756 | 973 | 865 | 756 |
| **INT8** | 865 | 756 | 973 | 865 | 756 |
| **BF16/FP16** | 432 | 378 | 486 | 432 | 378 |
| **TF32** | 216 | 189 | 243 | 216 | 189 |

### Vector Core Only

| Precision | 950PR Max | 950PR Min | 950DT Max | 950DT Mid | 950DT Min |
|-----------|-----------|-----------|-----------|-----------|-----------|
| **FP16/BF16** | 54 | 47 | 60 | 54 | 47 |
| **FP32** | 27 | 23 | 30 | 27 | 23 |
| **INT8** | 54 | 47 | 60 | 54 | 47 |
| **INT16** | 27 | 23 | 30 | 27 | 23 |
| **INT32** | 13 | 11 | 15 | 13 | 11 |
| **INT64** | 6 | 5 | 7 | 6 | 5 |

## Memory

| Parameter | 950PR | 950DT |
|-----------|-------|-------|
| **HBM Capacity** | 128/112 GB | 144/96 GB |
| **HBM Bandwidth** | 1.6/1.4 TB/s | 4 TB/s |
| **L2 Cache** | 128/112 MB | 128 MB |
| **L2 Cache Line** | 512B (4×128B Sector) | 512B (4×128B Sector) |
| **Per AI Core L1 Buffer** | 512 KB | 512 KB |
| **Per AI Core L0A Buffer** | 64 KB | 64 KB |
| **Per AI Core L0B Buffer** | 64 KB | 64 KB |
| **Per AI Core L0C Buffer** | 256 KB | 256 KB |
| **Per AI Core Unified Buffer** | 512 KB | 512 KB |

## AI CPU Subsystem

| Parameter | 950PR | 950DT |
|-----------|-------|-------|
| **CPU Core** | Linx816 (ARMv8-A) | Linx816 (ARMv8-A) |
| **Max Cores/Threads** | 8C/16T | 8C/16T |
| **Min Config** | 4C/8T | 6C/12T |
| **Per-Core L1 Cache** | 64 KB | 64 KB |
| **Per-Core L2 Cache** | 1 MB | 1 MB |
| **Per-Cluster L3 Cache** | 4 MB | 4 MB |
| **NEON Support** | Yes | Yes |

## DVPP (Media Processing)

| Module | 950PR | 950DT |
|--------|-------|-------|
| **VPC Cores** | 4/2 | 4/2 |
| **VPC Throughput** | 5760/2880 FPS @1080p | 5760/2880 FPS @1080p |
| **JPEGD Cores** | 8 | 8 |
| **JPEGD Throughput** | 4096 FPS @1080p | 4096 FPS @1080p |
| **JPEGD Max Resolution** | 32K × 32K | 32K × 32K |
| **JPEGE Cores** | 4/2 | 4/2 |
| **JPEGE Throughput** | 1024/512 FPS @1080p | 1024/512 FPS @1080p |
| **JPEGE Max Resolution** | 32K × 32K | 32K × 32K |

## Interconnect (IO)

| Parameter | Value |
|-----------|-------|
| **UB Protocol** | Unified Bus 2.0 |
| **SerDes** | 72× HiLink, up to 112 Gbps each |
| **UB Ports** | 18× x4 (supports x2, x1 down-lane) |
| **UB Bandwidth** | 2016 GB/s bidirectional |
| **UBoE Ports** | 2× x4 or 4× x2 |
| **UBoE Bandwidth** | 2× 400 Gbps (200 GB/s bidirectional) |
| **UBoE Speeds** | 400/200/100/50/25 Gbps per port |
| **PCIe** | Gen5 x16, 128 GB/s bidirectional |
| **PCIe Modes** | EP + RC (static selection) |
| **UB Programming** | UB Memory (sync Load/Store/Atomic), URMA (async), CCU |
| **UB Topologies** | Clos, Full Mesh+Clos, nD-Mesh |
| **UB On-Chip Switch** | Yes (IO Die forwarding, no DRAM bandwidth) |
| **CCU Algorithms** | Broadcast, ReduceScatter, AllGather, AllReduce, All2All, All2Allv |

## Scale

| Parameter | Value |
|-----------|-------|
| **Super Node** | Up to 8192 cards (via UB Switch) |
| **Max Cluster** | 128K+ cards |
| **UB Memory Pool** | Up to 128 TB shared memory access |

## Precision Format Comparison

| Format | Bits | Exponent Range | Scale Factor | Best For |
|--------|------|----------------|--------------|----------|
| **HiF8** | 8 | [-22, 15] (38 values) | None | Training + Inference |
| **MXFP8** | 8 | FP8 E4M3 + 8b scale | Yes | Inference |
| **FP8 E4M3** | 8 | [-15, 15] (18 values) | None | Training |
| **MXFP4** | 4 | FP4 + 8b scale | Yes | Extreme throughput |
| **BF16** | 16 | [-126, 127] | None | Training (baseline) |
| **FP16** | 16 | [-14, 15] | None | Inference |
| **TF32** | 19 (internal) | FP32 range | None | Training (NVIDIA compat) |
