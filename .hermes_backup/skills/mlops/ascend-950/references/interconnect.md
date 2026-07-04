# Ascend 950 Interconnect: Lingqu (Unified Bus 2.0)

## Overview

The Lingqu (灵衢) Unified Bus 2.0 is the universal interconnect fabric for Ascend 950. It unifies three communication paradigms under a single protocol:

| Paradigm | Interface | Semantics |
|----------|-----------|-----------|
| **Memory** | UB Memory | Load/Store/Atomic (synchronous) |
| **IO** | URMA | Async RDMA (Read/Write/Send/Atomic) |
| **Network** | UBoE | UB over standard Ethernet |

## Physical Layer

```
Ascend 950 Chip
├── 72 HiLink SerDes lanes @ up to 112 Gbps each
├── 18 × x4 Ports (configurable to x2, x1)
├── Total: 2016 GB/s bidirectional (UB Links)
├── 2 × x4 Ports shared with UBoE (400G each)
└── 4 × x4 Ports shared with PCIe 5.0 x16
```

**Port multiplexing**: UBoE and PCIe consume UB ports. Using 2×400G UBoE reduces available UB Link ports from 18 to 16.

## URMA (UB Remote Memory Access) — Async

### Communication Model

```
┌──────────┐                          ┌──────────┐
│ Core     │                          │ Remote   │
│ (AIC/AIV │   Doorbell ──────────→   │ Node     │
│  /CPU)   │                          │          │
│    │     │                          │    ↑     │
│    ▼     │                          │    │     │
│ Jetty Q  │── SQE ──→ Transport ──→  │  Memory   │
│    │     │                          │    │     │
│    ▼     │                          │    ▼     │
│  CQE ←── │←── Completion ─────────  │  Done    │
└──────────┘                          └──────────┘
```

### Operations

| Operation | Description |
|-----------|-------------|
| Write | Remote memory write |
| Write with ImmediateData | Write + inline 4B data |
| Write with Notify | Write + trigger remote event |
| Read | Remote memory read |
| Send | Message send |
| Send with ImmediateData | Message + inline data |
| Atomic FetchAdd | Atomic fetch-and-add |
| Atomic CompareAndSwap | Atomic CAS |

### Transport Modes

| Mode | Reliability | Bandwidth | Use Case |
|------|-------------|-----------|----------|
| **RTP** (Reliable Transport) | End-to-end retransmission | 4 Ports | Critical data, training |
| **CTP** (Compact Transport) | No retransmission | 9 Ports | Best-effort, inference |

Both modes support multi-path transport across multiple ports.

## UB Memory — Sync

### Communication Model

```
┌──────────┐                          ┌──────────┐
│ Core     │  Load/Store/Atomic       │ Remote   │
│ (AIC/AIV │ ───────────────────────→ │ Node      │
│  /CPU)   │                          │          │
│    │     │     UB Memory Decoder     │    │     │
│    ▼     │  (addr → node + offset)  │    ▼     │
│  UMMU    │ ───────────────────────→ │  UMMU    │
│ VA→PA    │                          │ PA→VA    │
└──────────┘                          └──────────┘
```

### Capabilities

- **Write**: Direct remote memory write
- **Read**: Direct remote memory read
- **AtomicStore**: Atomic store to remote memory
- **AtomicLoad**: Atomic load from remote memory
- **AtomicSwap**: Atomic swap with remote memory
- **AtomicCompareAndSwap**: Atomic CAS

### Address Space

- Up to **128 TB** shared memory space
- Host-to-Device and Device-to-Device access
- UMMU provides VA→PA translation and access control

## UBoE (UB over Ethernet)

```
┌─────────────┐         ┌─────────────┐
│ Ascend 950  │  UBoE   │  Ethernet   │
│  2×400G     │────────→│  Switch     │
│  Ports      │         │  (standard) │
└─────────────┘         └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │  Existing   │
                        │  DC Network │
                        └─────────────┘
```

- Direct UB protocol on Ethernet physical layer
- No protocol gateway or translation needed
- Port bifurcation: 1×400G or 2×200G, down to 25G
- Scale-out without proprietary switches

## CCU (Collective Communication Unit)

### Hardware-Offloaded Collectives

| Algorithm | Description |
|-----------|-------------|
| **Broadcast** | 1→N data distribution |
| **ReduceScatter** | Reduce then scatter results |
| **AllGather** | Gather distributed data |
| **AllReduce** | Reduce + Broadcast combined |
| **All2All** | Full permutation exchange |
| **All2Allv** | Variable-size All2All |

### Architecture

```
┌──────────────────────────────────────┐
│              CCU                      │
│  ┌────────────────────────────────┐  │
│  │ CCUM (Management)               │  │
│  │  - Mission queue (software API) │  │
│  │  - Instruction decode           │  │
│  ├────────────────────────────────┤  │
│  │ CCUA (Agent)                    │  │
│  │  - MemorySlice (data buffer)    │  │
│  │  - Reduce Unit (compute)        │  │
│  │  - URMA interface (data move)   │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### Workflow

1. STARS dispatches collective task to CCU via Mission queue
2. CCU decomposes into parallel fine-grained sub-tasks
3. For reduces: CCUA Reduce Unit computes locally
4. For data movement: CCU triggers URMA for remote transfers
5. Pipeline of compute + communication sub-tasks
6. Completion reported via Mission queue

**Key benefit**: Reduces bus bandwidth contention and frees AI Cores from communication work.

## UB On-Chip Switch

```
┌──────────────────────────────────────┐
│           IO Die                      │
│                                      │
│  Port0 ←──┐    ┌──→ Port4            │
│           │    │                      │
│  Port1 ←──┤ NoC├──→ Port5            │
│           │    │                      │
│  Port2 ←──┤    ├──→ Port6            │
│           │    │                      │
│  Port3 ←──┘    └──→ Port7            │
│                                      │
│  (Forwarding stays on IO Die)        │
│  (No DRAM bandwidth consumed)        │
│  (No AI Die involvement)             │
└──────────────────────────────────────┘
```

- **9 × x4 Ports** per IO Die support forwarding
- Traffic enters IO Die, checks route table, forwards out if not local
- Mix of injected + forwarded traffic supported
- Enables multi-hop topologies without dedicated switch chips

## Cluster Topologies

### nD-Mesh
```
C0──C1──C2──C3
│   │   │   │
C4──C5──C6──C7
│   │   │   │
C8──C9──C10─C11
```
- Direct chip-to-chip links
- Good for small-to-medium deployments
- Bisection bandwidth scales with dimension

### Clos (Fat-Tree)
```
        [Spine Switches]
         /    │    \
    [Leaf Switches]
     /   │   │   \
   C0  C1  C2  C3  ...
```
- Non-blocking with sufficient spine bandwidth
- Standard for large-scale training clusters
- Requires UB Switches

### Full Mesh + Clos Hybrid

- Full mesh within a node (e.g., 8 GPUs)
- Clos between nodes
- Balances local bandwidth and scale-out cost

## Super Node Architecture

### Scale

| Generation | Max Cards |
|-----------|-----------|
| Previous | 384 |
| **Ascend 950** | **8192** |

### Memory Pool

```
┌─────────────────────────────────────────┐
│        CPU Memory Pool (X TB)           │
│                 │                        │
│          ┌──────┴──────┐                 │
│          │   UB Fabric  │                 │
│          └──────┬──────┘                 │
│     ┌───────────┼───────────┐            │
│  ┌──▼──┐    ┌──▼──┐    ┌──▼──┐         │
│  │ NPU │    │ NPU │    │ NPU │  ...     │
│  │ 950 │    │ 950 │    │ 950 │          │
│  └─────┘    └─────┘    └─────┘          │
└─────────────────────────────────────────┘
```

- NPU directly accesses CPU memory via UB Memory semantic
- No storage protocol translation overhead
- High bandwidth, low latency to CPU memory pool
- Same mechanism for storage resource pools

### Ethernet Integration

```
┌──────────────────┐     ┌─────────────┐
│ Ascend 950       │     │ UB Switch   │
│ Super Node       │────→│ (UB→Eth     │──→ Ethernet DC Network
│ (UB Fabric)      │     │  gateway)   │
└──────────────────┘     └─────────────┘

OR directly:

┌──────────────────┐     ┌─────────────┐
│ Ascend 950       │UBoE │ Standard    │
│                  │────→│ Ethernet    │──→ Ethernet DC Network
│                  │     │ Switch      │
└──────────────────┘     └─────────────┘
```
