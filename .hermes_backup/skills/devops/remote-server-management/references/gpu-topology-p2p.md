# GPU Topology & P2P Snapshots

Snapshots captured 2026-05-27…28.

## 10.10.70.88 (oem88) Alltoall Benchmark Results (2026-06-22)

| Metric | 4-GPU | 8-GPU | 8/4 ratio |
|--------|------:|------:|----------:|
| Peak busbw | 35.46 GB/s | 25.25 GB/s | 0.71x |
| Avg busbw | 9.60 GB/s | 5.71 GB/s | 0.59x |

See `references/nccl-benchmark-results.md` for full per-size data and cross-server analysis.

## 10.10.70.96 (oem96) — 8× RTX PRO 6000 Blackwell SE

### Topology

```
        GPU0  GPU1  GPU2  GPU3  GPU4  GPU5  GPU6  GPU7  NIC0
GPU0     X    NODE  NODE  NODE  SYS   SYS   SYS   SYS   SYS
GPU1    NODE   X    NODE  NODE  SYS   SYS   SYS   SYS   SYS
GPU2    NODE  NODE   X    NODE  SYS   SYS   SYS   SYS   SYS
GPU3    NODE  NODE  NODE   X    SYS   SYS   SYS   SYS   SYS
GPU4     SYS   SYS   SYS   SYS   X    NODE  NODE  NODE  NODE
GPU5     SYS   SYS   SYS   SYS  NODE   X    NODE  NODE  NODE
GPU6     SYS   SYS   SYS   SYS  NODE  NODE   X    NODE  NODE
GPU7     SYS   SYS   SYS   SYS  NODE  NODE  NODE   X    NODE
NIC0     SYS   SYS   SYS   SYS  NODE  NODE  NODE  NODE   X
```

- NUMA 0: GPU0-3 (CPU 0-31,64-95)
- NUMA 1: GPU4-7 (CPU 32-63,96-127)
- NIC0 (rocep200s0f0) on NUMA 1
- No NVLink

### P2P Matrix

All 64 GPU pairs report **OK** (`nvidia-smi topo -p2p r`), including cross-NUMA SYS links. PCIe P2P can traverse QPI/UPI when ACS/IOMMU permits.

### PCIe Link Behavior

**No NVLink** — RTX PRO 6000 Blackwell SE has no NVLink support, pure PCIe topology.

**Critical: PCIe Gen5 works under load.** The GPU power-gates the PCIe link at idle (P8 → Gen1 ×16), but renegotiates to Gen5 ×16 (32 GT/s) once any NCCL workload runs (P0).

| State | Gen | Speed | Width | Effective BW |
|-------|:---:|:-----:|:-----:|:------------:|
| Idle (P8) | 1 | 2.5 GT/s | ×16 | ~0.5 GB/s |
| Under NCCL load (P0) | **5** | **32.0 GT/s** | ×16 | ~34 GB/s (2-card) |

**Proof:** Before running nccl-tests, `nvidia-smi` shows `Current: 1`. After a single `all_reduce_perf -b 1G -e 1G -f 2 -g 2`, all GPUs show `Current: 5`. Bridge sysfs confirms: `32.0 GT/s PCIe`.

| Metric | Value |
|--------|-------|
| Max capable (device) | Gen5 ×16 (32.0 GT/s) |
| Max capable (upstream bridge) | Gen5 ×16 (32.0 GT/s) |
| Negotiated under load | Gen5 ×16 (32.0 GT/s) |
| Theoretical BW (Gen5 ×16, unidirectional) | ~63 GB/s |
| Measured 2-card all_reduce peak (Gen5) | **34.29 GB/s** |
| Measured 8-card all_reduce BusBW peak (Gen5) | **39.53 GB/s** |

**Key insight — "PCIe Gen1 lock" is MISLEADING:** When idle (P8), the GPU power-gates the PCIe link and renegotiates down to Gen1. UNDER LOAD it achieves Gen5 ×16. Always test under load before concluding the link is stuck.

### NCCL Benchmark Results (PCIe Gen5, Quick Mode)

| Metric | 2-card (within NUMA) | 8-card (cross-NUMA) |
|--------|:--------------------:|:-------------------:|
| Peak AlgoBW | **34.29 GB/s** | 22.59 GB/s |
| Peak BusBW | **34.29 GB/s** | **39.53 GB/s** |
| Avg BusBW | 14.87 GB/s | 16.59 GB/s |
| Latency @ 8B | 14.95 us | 36.91 us |

- 2-card within NUMA achieves full PCIe Gen5 ×16 unidirectional saturation (~34 GB/s)
- 8-card cross-NUMA limited by QPI/UPI fabric to ~39.5 GB/s BusBW
- Full collective suite results in `nccl_benchmark_20260528_190107.md` on 70.96

### Diagnostic Commands

```bash
# Idle state (will show Gen1 — this IS NORMAL!)
nvidia-smi -q -i 0 | grep -A5 'PCIe Generation'
nvidia-smi -q -i 0 | grep 'Performance State'
cat /sys/bus/pci/devices/0000:15:01.0/current_link_speed
cat /sys/bus/pci/devices/0000:16:00.0/current_link_speed

# After load — this shows the TRUE negotiated speed
cd ~/work/bandwidth_test/nccl-tests/build && \
./all_reduce_perf -b 256M -e 256M -f 2 -g 8 2>&1 | tail -3 && \
nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.gen.max --format=csv,noheader

# Wait for all GPUs to be out of P8 before checking
# The bridge and GPU sysfs values update AFTER workload finishes
cat /sys/bus/pci/devices/0000:15:01.0/current_link_speed   # should show "32.0 GT/s PCIe"
cat /sys/bus/pci/devices/0000:16:00.0/current_link_speed   # should show "32.0 GT/s PCIe"

# Bridge capabilities
cat /sys/bus/pci/devices/0000:15:01.0/max_link_speed   # 32.0 GT/s
lspci -s 15:01.0 -vn                                    # Intel 352a bridge
```

**Rapid diagnostic (one-liner):**
```bash
ssh 70.96 "cd ~/work/bandwidth_test/nccl-tests/build && ./all_reduce_perf -b 1G -e 1G -f 2 -g 2 2>&1 | tail -3 && nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.gen.max --format=csv,noheader"
```

Each GPU behind its own Intel 352a PCIe bridge on the root bus:

| GPU | Bus | Bridge | NUMA |
|-----|-----|--------|------|
| 0 | 16:00.0 | 15:01.0 | 0 |
| 1 | 27:00.0 | 26:01.0 | 0 |
| 2 | 38:00.0 | 37:01.0 | 0 |
| 3 | 5A:00.0 | 59:01.0 | 0 |
| 4 | 98:00.0 | 97:01.0 | 1 |
| 5 | A8:00.0 | A7:01.0 | 1 |
| 6 | B8:00.0 | B7:01.0 | 1 |
| 7 | D8:00.0 | D7:01.0 | 1 |

### NCCL Benchmark Results (Quick Mode)

| Metric | 2-card | 8-card |
|--------|:------:|:------:|
| Peak AlgoBW | 17.49 GB/s | 12.18 GB/s |
| Peak BusBW | 17.49 GB/s | 21.32 GB/s |
| Avg BusBW | 8.21 GB/s | 9.21 GB/s |
| Latency @ 8B | 14.85 us | 56.56 us |

- 2-card limited by single PCIe Gen4 ×16 within NUMA (~17.5 GB/s actual vs ~31.5 GB/s theoretical)
- 8-card cross-NUMA capped at ~21 GB/s by QPI/UPI fabric
- 8× RTX 5090 on 70.88 (single NUMA, PCIe 5.0) achieves ~31 GB/s for comparison

## 10.10.70.88 (oem88) — 8× RTX 5090 32GB

### Topology

```
        GPU0  GPU1  GPU2  GPU3  GPU4  GPU5  GPU6  GPU7  NIC0  NIC1
GPU0     X    NODE  NODE  NODE  SYS   SYS   SYS   SYS   SYS   SYS
GPU1    NODE   X    NODE  NODE  SYS   SYS   SYS   SYS   SYS   SYS
GPU2    NODE  NODE   X    NODE  SYS   SYS   SYS   SYS   SYS   SYS
GPU3    NODE  NODE  NODE   X    SYS   SYS   SYS   SYS   SYS   SYS
GPU4     SYS   SYS   SYS   SYS   X    NODE  NODE  NODE  NODE  NODE
GPU5     SYS   SYS   SYS   SYS  NODE   X    NODE  NODE  NODE  NODE
GPU6     SYS   SYS   SYS   SYS  NODE  NODE   X    NODE  NODE  NODE
GPU7     SYS   SYS   SYS   SYS  NODE  NODE  NODE   X    NODE  NODE
NIC0     SYS   SYS   SYS   SYS  NODE  NODE  NODE  NODE   X    PIX
NIC1     SYS   SYS   SYS   SYS  NODE  NODE  NODE  NODE  PIX    X
```

- NUMA 0: GPU0-3 (CPU 0-47,96-143)
- NUMA 1: GPU4-7 (CPU 48-95,144-191)
- NIC0 (mlx5_0) / NIC1 (mlx5_1) on NUMA 1
- **No NVLink** — RTX 5090 has no NVLink
- CPU: 2× Xeon Platinum 8558P (48c/96t per socket, 260 MB L3 per socket, 192 threads total)
- PCIe: Gen5 ×16 (confirmed under load), idle shows Gen1 (power-gating, normal)
- NCCL: 2.28.9+cuda13.0

### GPU PCI Bus Mapping

| GPU | Bus | Device ID | Class | NUMA |
|-----|-----|-----------|-------|------|
| 0 | 16:00.0 | 10de:2b85 | 0300 (VGA) | 0 |
| 1 | 27:00.0 | 10de:2b85 | 0300 (VGA) | 0 |
| 2 | 38:00.0 | 10de:2b85 | 0300 (VGA) | 0 |
| 3 | 5a:00.0 | 10de:2b85 | 0300 (VGA) | 0 |
| 4 | 98:00.0 | 10de:2b85 | 0300 (VGA) | 1 |
| 5 | a8:00.0 | 10de:2b85 | 0300 (VGA) | 1 |
| 6 | b8:00.0 | 10de:2b85 | 0300 (VGA) | 1 |
| 7 | d8:00.0 | 10de:2b85 | 0300 (VGA) | 1 |

Note: RTX 5090 reports as class 0300 (VGA), while RTX PRO 6000 reports as class 0302 (3D controller). This may affect NCCL algorithm selection.

## 10.10.70.98 (oem98) — 8× RTX PRO 6000 Blackwell SE

### Topology

Identical topology matrix to 70.96.

- NUMA 0: GPU0-3 (CPU 0-31,64-95)
- NUMA 1: GPU4-7 (CPU 32-63,96-127)
- NIC0/1 on NUMA 1
- **No NVLink** — confirmed by `nvidia-smi nvlink --status`: "Device does not have or support NVlink"
- CPU: 2× Xeon Gold 6530 (32c/64t per socket, 160 MB L3 per socket, 128 threads total)
- PCIe: Gen5 ×16 (confirmed under load), idle shows Gen1 (power-gating, normal)
- NCCL: 2.30.4+cuda13.2

### GPU PCI Bus Mapping

| GPU | Bus | Device ID | Class | NUMA |
|-----|-----|-----------|-------|------|
| 0 | 16:00.0 | 10de:2bb5 | 0302 (3D controller) | 0 |
| 1 | 27:00.0 | 10de:2bb5 | 0302 (3D controller) | 0 |
| 2 | 38:00.0 | 10de:2bb5 | 0302 (3D controller) | 0 |
| 3 | 5a:00.0 | 10de:2bb5 | 0302 (3D controller) | 0 |
| 4 | 98:00.0 | 10de:2bb5 | 0302 (3D controller) | 1 |
| 5 | a8:00.0 | 10de:2bb5 | 0302 (3D controller) | 1 |
| 6 | b8:00.0 | 10de:2bb5 | 0302 (3D controller) | 1 |
| 7 | d8:00.0 | 10de:2bb5 | 0302 (3D controller) | 1 |

### Alltoall Benchmark Results (2026-06-22)

| Metric | 4-GPU | 8-GPU | 8/4 ratio |
|--------|------:|------:|----------:|
| Peak busbw | 33.53 GB/s | 13.05 GB/s | 0.38x |
| Avg busbw | 8.68 GB/s | 3.70 GB/s | 0.43x |

See `references/nccl-benchmark-results.md` for full per-size data.
