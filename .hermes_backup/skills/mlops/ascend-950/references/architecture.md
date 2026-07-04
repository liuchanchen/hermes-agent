# Ascend 950 Architecture Deep Dive

## Chiplet Topology

```
┌─────────────────────────────────────────────────┐
│                  Ascend 950 Chip                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  AI Die 0 │  │  AI Die 1 │  │ HBM x4-8 │       │
│  │ 18 AIC    │  │ 18 AIC    │  │ (PR:8)   │       │
│  │ 36 AIV    │  │ 36 AIV    │  │ (DT:4)   │       │
│  └─────┬────┘  └─────┬────┘  └──────────┘       │
│        │ D2D Clink   │                             │
│  ┌─────┴─────────────┴────┐                       │
│  │       IO Die × 2        │                       │
│  │  9 Ports ×4 HiLink each │                       │
│  │  UBoE, PCIe controllers │                       │
│  └─────────────────────────┘                       │
└─────────────────────────────────────────────────┘
```

**Key principle**: UMA across all dies — hardware cache coherency between AI Dies, software-transparent.

## AI Core (DaVinci Core 3rd Gen)

Each AI Core contains:

```
┌────────────────────────────────────────┐
│           AI Subsystem (×36)            │
│  ┌──────────────┐  ┌──────────────────┐│
│  │  Cube Core   │  │  Vector Core ×2  ││
│  │  (AIC)       │  │  (AIV)           ││
│  │              │  │                  ││
│  │  L0A: 64KB   │  │  Unified Buffer  ││
│  │  L0B: 64KB   │  │  512KB           ││
│  │  L0C: 256KB  │  │  RegFile         ││
│  │              │  │  Dual-Issue ALU  ││
│  └──────┬───────┘  └────────┬─────────┘│
│         │    CV Fusion       │          │
│         └────────────────────┘          │
│         L1 Buffer: 512KB                │
└────────────────────────────────────────┘
```

### Cube Core (AIC — AI Cube Core)

- **Primary function**: Matrix multiply-accumulate (GEMM, Attention)
- **Precision formats**: MXFP4, MXFP8, HiF8, FP8, BF16, FP16, TF32, INT8
- **Key improvements over Gen2**:
  - MXFP4 delivers 4× BF16 peak TFLOPS
  - Larger L0C Buffer (256KB) for flexible tiling
  - On-the-fly quantization: FP32→BF16/FP16/FP8 during writeback to Unified Buffer
  - NZ→ND/DN layout conversion at writeback

### Vector Core (AIV — AI Vector Core)

- **Primary function**: Element-wise ops, activation functions, normalization
- **2× FP32/FP16** over previous generation
- **Dual-issue register-based SIMD** architecture
- **New RegFile** between Unified Buffer and ALU for higher bandwidth
- **SIMD/SIMT hybrid** (see programming-model.md)
- Native BF16, broad format conversion instructions
- Optimized microarchitecture for Softmax, GELU

### CV Fusion (Cube-Vector Data Path)

- Direct data channel between Cube L1 Buffer and Vector Unified Buffer
- Reduces L2 data exchange
- On-the-fly precision/layout conversion during transfer
- Critical for FlashAttention: Cube computes QK^T, Vector applies softmax, result feeds back to Cube

## Memory Hierarchy

```
┌──────────────────────────────────────────────────┐
│ HBM (Global Memory)                               │
│ 950PR: 128GB @ 1.6 TB/s                          │
│ 950DT: 144GB @ 4.0 TB/s                          │
├──────────────────────────────────────────────────┤
│ L2 Cache: 128MB (UMA, cross-die coherent)        │
│ - 512B cache line, 128B Sector                   │
│ - Multi-bank, simultaneous R/W per bank           │
│ - L2 Hint: allocate/non-allocate per buffer       │
│ - CMO: Prefetch, Writeback, Invalidate, Flush    │
├──────────────────────────────────────────────────┤
│ L1 Buffer: 512KB per AI Core                     │
├──────────────────┬───────────────────────────────┤
│ Cube Side        │ Vector Side                   │
│ L0A: 64KB        │ Unified Buffer: 512KB         │
│ L0B: 64KB        │ RegFile                        │
│ L0C: 256KB       │                                │
└──────────────────┴───────────────────────────────┘
```

### L2 Cache Management

**L2 Hint strategies**:
- `allocate`: Data likely reused by next task → cache in L2
- `non-allocate`: Data not immediately reused → bypass L2, write directly to HBM
- Prevents cache pollution from transient data

**CMO (Cache Maintenance Operations)**:
- `Prefetch`: Load data into L2 before needed
- `Writeback`: Force dirty data to HBM
- `Invalidate`: Mark cache lines invalid
- `Flush`: Writeback + Invalidate

**Sector Cache**: 512B cache line split into 4×128B sectors. 128B/256B accesses hit only needed sectors, improving efficiency for small, scattered reads.

### HBM RAS (Reliability, Availability, Serviceability)

- Online ECC
- Patrol scrubbing (detect weak rows, writeback or isolate)
- Spare rows for transparent row-failure isolation

## STARS 2.0 (System Task and Resource Scheduler)

```
┌────────────────────────────────────────┐
│              STARS 2.0                  │
│  ┌──────────────────────────────────┐  │
│  │ Host → 2048 Task Streams          │  │
│  │  ↓ prefetch → schedule → report   │  │
│  ├──────────────────────────────────┤  │
│  │ Concurrent Scheduling:            │  │
│  │  • AI Cores (AIC/AIV)            │  │
│  │  • AI CPU (16 tasks)              │  │
│  │  • Host CPU (64 tasks)            │  │
│  │  • DVPP (VPC, JPEGD, JPEGE)      │  │
│  │  • SDMA (32 channels)             │  │
│  │  • CCU (32 tasks)                 │  │
│  │  • UB Jetty (64)                  │  │
│  ├──────────────────────────────────┤  │
│  │ HSCB: ns-level control bus to AI  │  │
│  │ Cores (separate from NoC data)    │  │
│  ├──────────────────────────────────┤  │
│  │ Resource Partitioning:            │  │
│  │  • AIC/AIV/SDMA: up to 16 pools  │  │
│  │  • Other accelerators: up to 8    │  │
│  │  • VM binding per pool            │  │
│  ├──────────────────────────────────┤  │
│  │ Group Scheduling: up to 8 groups  │  │
│  │  • Per-die affinity for L2 reuse  │  │
│  ├──────────────────────────────────┤  │
│  │ Sync: 128K 1-bit or 4096 32-bit   │  │
│  │ flags for inter-task sync          │  │
│  ├──────────────────────────────────┤  │
│  │ Profiling: TOP-DOWN real-time     │  │
│  │  • Task timeline, compute cost,   │  │
│  │    bandwidth, power               │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

### Key STARS 2.0 Features

1. **2048 task streams**: Host offloads entire task graphs to device — STARS prefetches, schedules, reports completion
2. **HSCB (High Speed Control Bus)**: Dedicated ns-latency bus for AI Core dispatch, separate from data NoC — no congestion
3. **Group scheduling**: Assign AI Cores to die-local groups for L2 Cache locality
4. **Resource pools**: Hardware-enforced isolation for multi-tenant/virtualization scenarios
5. **Real-time profiling**: TOP-DOWN analysis without instrumentation overhead

## DVPP (DaVinci Vision Pre-Processing)

### VPC (Vision Processing Core)

- Resize, Crop, Padding
- Upsample/Downsample (UVDEC/UVUP)
- Color Space Conversion, HSV adjustment
- Affine/Perspective transforms
- Pixel augmentation (PixAug)
- API-compatible with: OpenCV, TensorFlow, TorchVision, Pillow, DALI
- STARS direct hardware scheduling

### JPEGD (Decoder)

- Max resolution: 32768 × 32768
- Formats: YUV444/422/420/440/400 (8-bit)
- Region-of-interest decode
- Compatible with libjpeg-turbo v2.0.2

### JPEGE (Encoder)

- Max resolution: 32768 × 32768
- Formats: YUV420 semi-planar, YUV422 packed, YUV444 planar/packed, YUV400
- Baseline JPEG (Sequential DCT)
