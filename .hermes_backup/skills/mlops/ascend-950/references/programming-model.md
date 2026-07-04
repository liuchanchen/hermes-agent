# Ascend 950 Programming Model

## DaVinci Core Programming Paradigm

### Ascend C

Ascend C is the kernel-level programming language for DaVinci Core. It provides:

- **Operator-level API**: Define compute kernels that run on AI Cores
- **Memory hierarchy control**: Explicit management of L1/L0/UB buffers
- **Data movement**: DMA descriptors for HBM↔L2↔L1↔UB transfers
- **Synchronization**: Events, barriers, BufferID locks

### Compute Model

```
┌─────────────────────────────────────────┐
│         Host (x86 / Kunpeng)            │
│  ┌───────────────────────────────────┐  │
│  │ CANN Runtime                       │  │
│  │  ↓ Task Graph (2048 streams max)   │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │ PCIe 5.0
┌──────────────▼──────────────────────────┐
│         Device (Ascend 950)              │
│  ┌───────────────────────────────────┐  │
│  │ STARS 2.0 Scheduler               │  │
│  └───────────────────────────────────┘  │
│  ┌─────────┐  ┌─────────┐              │
│  │ AIC (CU)│  │ AIV (VE)│  ... ×36    │
│  └─────────┘  └─────────┘              │
└─────────────────────────────────────────┘
```

## HiF8 Format

HiF8 is Huawei's proprietary 8-bit floating-point format designed to balance precision and dynamic range without requiring a shared scale factor (unlike MXFP8).

### Encoding

```
Bit layout (8 bits total):
┌───────┬─────────┐
│  Dot  │ Mantissa│  + implicit sign bit
└───────┴─────────┘
```

- **Dot field**: Variable-length prefix code that indicates:
  - Exponent width
  - Whether value is denormal
- **Exponent**: Sign-magnitude encoding with 1 hidden bit (no redundancy between widths)
- **Mantissa**: Variable width depending on exponent range

### Properties

| Property | HiF8 | FP8 E4M3 | MXFP8 | BF16 |
|----------|------|----------|-------|------|
| Total bits | 8 | 8 | 8 (+ shared scale) | 16 |
| Exponent values | 38 | 18 | 18 (+ scale) | 254 |
| Dynamic range | Near FP16 | Limited | Scale-dependent | Full FP32 range |
| Scale factor needed | No | No | Yes (8-bit) | No |
| Special values | 4 (ZERO, NAN, +INF, -INF) | | | |

### Tapered Precision

HiF8 uses tapered precision — values near 1.0 have highest precision (more mantissa bits), values far from 1.0 have lower precision but wider range. Precision degrades gradually (1 bit at a time), no abrupt jumps.

### Special Value Encodings

| Value | Encoding |
|-------|----------|
| ZERO | `00000000` |
| NAN | `10000000` |
| +INF | `01101111` |
| -INF | `11101111` |

### When to Use HiF8

- **Training**: Better gradient preservation than FP8 E4M3 due to wider dynamic range
- **Inference**: Higher accuracy than INT8 quantization with similar throughput
- **KV Cache compression**: Store attention keys/values in HiF8 to reduce memory

## SIMD/SIMT Hybrid Programming

### Architecture

```
Vector Function (VF) = basic execution unit
├── SIMD VF: Single instruction, multiple data
│   - Dual-issue ALU
│   - Out-of-order execution
│   - High throughput for regular patterns
│   - Use for: element-wise, BatchNorm, LayerNorm, ReLU/GELU
│
└── SIMT VF: Single instruction, multiple threads
    - Independent address spaces per thread
    - Branch divergence tolerance
    - Use for: Gather/Scatter, Hash Insert, sparse operations
```

### Programming Model

- Define functions as **Vector Functions (VF)**
- Each VF can be implemented in SIMD or SIMT mode
- Mix SIMD and SIMT VFs in the same kernel
- Fast context switch between SIMD and SIMT VFs
- **Default: SIMD-first** — most compute goes through SIMD; SIMT for irregular patterns only

### Typical Partitioning

```
Kernel: FlashAttention Forward
├── QK^T matmul        → Cube Core (GEMM)
├── Scale + Mask        → Vector SIMD (element-wise)
├── Softmax:
│   ├── Max reduction   → Vector SIMD
│   ├── Exp             → Vector SIMD
│   └── Sum reduction   → Vector SIMD
├── Attention × V       → Cube Core (GEMM)
└── Gather/Scatter ops  → Vector SIMT (if irregular access)
```

## NDDMA (N-Dimensional DMA)

### Overview

NDDMA hardens address generation logic for multi-dimensional data rearrangement, replacing complex software loops with single hardware instructions.

### Capabilities

- **Up to 5 dimensions** of data rearrangement
- **Combined operations**: Move + Reshape + Transpose in single instruction
- **Automatic cache optimization**: Coalesces small reads into 128B cache-line reads
- **Source**: Global Memory (HBM)
- **Destination**: Vector Core Unified Buffer

### Example

```
Input in Global Memory (interleaved blocks):
[1][x][x][2][x][x][3][x][x]...

NDDMA parameters:
  src_base = &input[0]
  dst_base = &UB[offset]
  block_size = 1 element
  stride = 3 elements
  count = 3

Result in Unified Buffer:
[1][2][3]
```

### Use Cases

- NCHW ↔ NHWC layout conversion
- Matrix transpose during data load
- Gathering non-contiguous tensor slices
- Padding/trimming during DMA

## BufferID Synchronization

New synchronization primitive replacing set_flag/wait_flag:

```
// Producer
buf_id = get_buf()    // Acquire buffer (lock)
// ... fill buffer with data ...
rel_buf(buf_id)        // Release buffer (unlock)

// Consumer
buf_id = get_buf()    // Block until buffer available
// ... read data from buffer ...
rel_buf(buf_id)        // Return buffer to pool
```

**Advantages over flags**:
- Self-contained: buffer ownership is explicit, no cross-pipeline coupling
- Pipeline isolation: each producer-consumer pair uses independent BufferID
- Deadlock prevention: hardware-enforced acquire/release pairing

## FlashAttention Optimization on Ascend 950

### Hardware Features for FlashAttention

1. **CV Fusion data path**: Cube computes QK^T → result flows directly to Vector for softmax → flows back to Cube for attention×V
2. **Softmax acceleration**: Vector Core has optimized microarchitecture for exp, max reduction, sum reduction
3. **Low-precision formats**: MXFP8/MXFP4 for Q, K, V storage — reduces memory bandwidth
4. **On-the-fly conversion**: Cube results quantized during writeback, Vector reads in native format

### Performance

- **1.5–2×** single-core performance vs previous generation
- Combined with compute-communication overlap for multi-GPU training

## CANN Software Stack

```
┌────────────────────────────────────────┐
│         Application Framework          │
│  (PyTorch, TensorFlow, MindSpore)      │
├────────────────────────────────────────┤
│       CANN Acceleration Libraries      │
│  (BLAS, FFT, RNG, DVPP, CCU)          │
├────────────────────────────────────────┤
│       Ascend C Operator API            │
│  (Kernel programming for DaVinci)      │
├────────────────────────────────────────┤
│       Graph Compiler (GE)              │
│  (Fusion, tiling, scheduling)          │
├────────────────────────────────────────┤
│       Runtime (Runtime)                │
│  (Task dispatch, memory, streams)      │
├────────────────────────────────────────┤
│       Driver (Driver)                  │
│  (Device management, PCIe transport)   │
└────────────────────────────────────────┘
```

All layers are open-source — developers have full access to operator implementations.
