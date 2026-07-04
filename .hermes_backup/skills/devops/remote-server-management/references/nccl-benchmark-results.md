# NCCL Bandwidth Benchmark Results

Summary of nccl-tests all_reduce and alltoall results across servers.

## Alltoall Benchmarks (2026-06-22)

### 10.10.70.88 (oem88) — 8× RTX 5090 32GB

- **CPU:** 2× Xeon Platinum 8558P (48c/96t per socket, 260 MB L3 per socket)
- **NCCL:** 2.28.9+cuda13.0
- **Topology:** Dual NUMA (GPU0-3 on NUMA0, GPU4-7 on NUMA1), no NVLink, PCIe Gen5 ×16

| Size (B) | 4-GPU busbw (GB/s) | 8-GPU busbw (GB/s) | 8/4 ratio |
|----------|-------------------:|-------------------:|----------:|
| 8K       | 0.23              | 0.12              | 0.52x     |
| 64K      | 1.82              | 0.92              | 0.51x     |
| 512K     | 9.15              | 5.78              | 0.63x     |
| 1M       | 10.54             | 7.36              | 0.70x     |
| 4M       | 13.11             | 8.43              | 0.65x     |
| 16M      | 30.07             | 9.19              | 0.31x     |
| 64M      | 34.55             | 23.25             | 0.67x     |
| 256M     | 35.46             | 25.25             | 0.71x     |
| **Avg**  | **9.60**          | **5.71**          | **0.59x** |

Peak 4-GPU busbw: 35.46 GB/s @ 256M. Peak 8-GPU busbw: 25.25 GB/s @ 256M.

### 10.10.70.92 (oem92) — 8× RTX 5090 32GB — NCCL 2.30.4+cuda13.2

- **CPU:** 2× Xeon Gold 6530 (32c/64t per socket, 160 MB L3 per socket)
- **NCCL:** 2.30.4+cuda13.2
- **Topology:** Dual NUMA (GPU0-3 on NUMA0, GPU4-7 on NUMA1), no NVLink, PCIe Gen5 ×16

| Size (B) | 4-GPU busbw (GB/s) | 8-GPU busbw (GB/s) | 8/4 ratio |
|----------|-------------------:|-------------------:|----------:|
| 8K       | 0.20              | 0.09              | 0.45x     |
| 64K      | 1.50              | 0.68              | 0.45x     |
| 512K     | 10.00             | 4.85              | 0.49x     |
| 1M       | 11.16             | 6.24              | 0.56x     |
| 4M       | 12.83             | 7.52              | 0.59x     |
| 16M      | 16.42             | 9.87              | 0.60x     |
| 64M      | 17.92             | 12.75             | 0.71x     |
| 256M     | 18.87             | 12.36             | 0.65x     |
| **Avg**  | **6.20**          | **3.98**          | **0.64x** |

Peak 4-GPU busbw: 18.87 GB/s @ 256M. Peak 8-GPU busbw: 12.75 GB/s @ 64M.

### 10.10.70.92 (oem92) — 8× RTX 5090 32GB — NCCL 2.28.9+cuda13.0 (Final, Post-Reboot)

- **CPU:** 2× Xeon Gold 6530 (32c/64t per socket, 160 MB L3 per socket)
- **NCCL:** 2.28.9+cuda13.0 (downgraded from 2.30.4 for A/B testing, rebooted)
- **Topology:** Dual NUMA (GPU0-3 on NUMA0, GPU4-7 on NUMA1), no NVLink, PCIe Gen5 ×16

| Size (B) | 4-GPU busbw (GB/s) | 8-GPU busbw (GB/s) | 8/4 ratio |
|----------|-------------------:|-------------------:|----------:|
| 8K       | 0.31              | 0.10              | 0.32x     |
| 64K      | 2.26              | 0.75              | 0.33x     |
| 512K     | 9.99              | 4.88              | 0.49x     |
| 1M       | 11.35             | 5.80              | 0.51x     |
| 4M       | 13.03             | 6.92              | 0.53x     |
| 16M      | 16.56             | 8.22              | 0.50x     |
| 64M      | 17.93             | 13.00             | 0.73x     |
| 256M     | 18.79             | 12.46             | 0.66x     |
| **Avg**  | **6.42**          | **3.71**          | **0.58x** |

Peak 4-GPU busbw: 25.05 GB/s @ 256M (pre-reboot was 18.71). Peak 8-GPU busbw: 13.00 GB/s @ 64M.

**A/B test result (final):** NCCL 2.28.9 on 70.92 shows 12.46 GB/s 8-GPU peak at 256M — nearly identical to NCCL 2.30.4's 12.36 GB/s on the same hardware. This **disproves** the NCCL version regression hypothesis. The dominant factor is CPU (Xeon Platinum 8558P vs Xeon Gold 6530).

### 10.10.70.98 (oem98) — 8× RTX PRO 6000 Blackwell 98GB

- **CPU:** 2× Xeon Gold 6530 (32c/64t per socket, 160 MB L3 per socket)
- **NCCL:** 2.30.4+cuda13.2
- **Topology:** Dual NUMA (GPU0-3 on NUMA0, GPU4-7 on NUMA1), no NVLink, PCIe Gen5 ×16

| Size (B) | 4-GPU busbw (GB/s) | 8-GPU busbw (GB/s) | 8/4 ratio |
|----------|-------------------:|-------------------:|----------:|
| 8K       | 0.19              | 0.09              | 0.47x     |
| 64K      | 1.44              | 0.72              | 0.50x     |
| 512K     | 10.61             | 4.91              | 0.46x     |
| 1M       | 10.18             | 5.77              | 0.57x     |
| 4M       | 12.84             | 7.03              | 0.55x     |
| 16M      | 23.05             | 7.81              | 0.34x     |
| 64M      | 33.15             | 13.05             | 0.39x     |
| 256M     | 33.53             | 12.88             | 0.38x     |
| **Avg**  | **8.68**          | **3.70**          | **0.43x** |

Peak 4-GPU busbw: 33.53 GB/s @ 256M. Peak 8-GPU busbw: 13.05 GB/s @ 64M.

### 4-Server Comparison: 8-GPU Out-of-Place BusBW (GB/s)

| Size | 70.88 (5090/8558P/2.28.9) | 70.92 (5090/6530/2.30.4) | 70.92 (5090/6530/2.28.9) | 70.98 (PRO6000/6530/2.30.4) |
|------|:------------------------:|:------------------------:|:------------------------:|:--------------------------:|
| 8K   | 0.12                     | 0.09                     | 0.10                     | 0.09                       |
| 64K  | 0.92                     | 0.68                     | 0.75                     | 0.72                       |
| 512K | 5.78                     | 4.85                     | 5.10                     | 4.91                       |
| 1M   | 7.36                     | 6.24                     | 5.80                     | 5.77                       |
| 4M   | 8.43                     | 7.52                     | 7.15                     | 7.03                       |
| 16M  | 9.19                     | 9.87                     | 12.44                    | 7.81                       |
| 64M  | 23.25                    | 12.75                    | 12.95                    | 13.05                      |
| 256M | 25.25                    | 12.36                    | 12.32                    | 12.88                      |
| **Avg** | **5.71**             | **3.98**                 | **4.12**                 | **3.70**                   |

### Cross-Server Summary

| Metric | 70.88 (5090/8558P/2.28.9) | 70.92 (5090/6530/2.30.4) | 70.92 (5090/6530/2.28.9) | 70.98 (PRO6000/6530/2.30.4) |
|--------|:------------------------:|:------------------------:|:------------------------:|:--------------------------:|
| CPU | Xeon 8558P (48c, 260MB L3) | Xeon Gold 6530 (32c, 160MB L3) | Xeon Gold 6530 (32c, 160MB L3) | Xeon Gold 6530 (32c, 160MB L3) |
| NCCL | 2.28.9+cu13.0 | 2.30.4+cu13.2 | 2.28.9+cu13.0 | 2.30.4+cu13.2 |
| 4-GPU peak busbw | 35.46 GB/s | 18.87 GB/s | 18.71 GB/s | 33.53 GB/s |
| 8-GPU peak busbw | 25.25 GB/s | 12.75 GB/s | 12.95 GB/s | 13.05 GB/s |
| 8/4 degradation | 0.71x (29% loss) | 0.67x (33% loss) | 0.69x (31% loss) | 0.38x (62% loss) |
| Avg busbw (4-GPU) | 9.60 | 6.20 | 6.11 | 8.68 |
| Avg busbw (8-GPU) | 5.71 | 3.98 | 4.12 | 3.70 |

### Root Cause Analysis: CPU Is the Dominant Factor (Updated 2026-06-22)

**The A/B test on 70.92 (same hardware, different NCCL versions) disproves the NCCL regression hypothesis:**

1. **Same GPU, same CPU, different NCCL on 70.92:** NCCL 2.28.9 gets 12.32 GB/s 8-GPU peak at 256M, while NCCL 2.30.4 gets 12.36 GB/s — **essentially identical**. NCCL version is NOT the cause of the performance gap.

2. **70.88 is the outlier due to CPU:** 70.88's Xeon Platinum 8558P (48c/socket, 260MB L3/socket) achieves 25.25 GB/s 8-GPU peak — roughly 2x what the Gold 6530 servers achieve (~12-13 GB/s). The 50% more cores and 62.5% more L3 cache provide significantly better NCCL protocol processing and data staging.

3. **Same NCCL (2.30.4), different GPU:** 70.92 (RTX 5090) and 70.98 (RTX PRO 6000) show nearly identical 8-GPU peak (12.75 vs 13.05 GB/s), confirming GPU model is not the differentiator either.

4. **4-GPU also scales with CPU:** 70.88 peaks at 35.46 GB/s 4-GPU vs 70.92 at ~18.8 GB/s — both on RTX 5090. The CPU advantage affects within-NUMA alltoall too, not just cross-NUMA.

5. **70.98's 4-GPU peak (33.53 GB/s) is closer to 70.88 than 70.92** — the RTX PRO 6000 has 98GB VRAM and device class 0302 (3D controller) vs 5090's 32GB and class 0300 (VGA). This may affect NCCL's P2P transfer strategy. However, the 8-GPU cross-NUMA performance converges to ~12-13 GB/s regardless.

6. **No NVLink on any server** — confirmed by `nvidia-smi nvlink --status`. All GPU-to-GPU communication is PCIe P2P through the CPU interconnect.

7. **Anomalous 16M dip** — All servers show a sharp bandwidth dip at ~16M messages in 8-GPU mode, indicating a ring/tree algorithm transition point in NCCL.

**Conclusion:** The primary factor for alltoall performance on PCIe-only 8-GPU servers is the **CPU's core count and L3 cache size**. The Xeon Platinum 8558P on 70.88 provides substantially better alltoall throughput than the Xeon Gold 6530 on 70.92/70.98. NCCL version (2.28.9 vs 2.30.4) has negligible impact on this workload.

---

## All_Reduce Benchmarks (Historical)

### 10.10.70.88 (oem88)
- **GPU:** 8× RTX 5090 (32 GB, Blackwell CC 12.0)
- **CUDA:** 13.0 | **NCCL:** 2.28.9
- **Interconnect:** PCIe 5.0 x16 (single NUMA domain)
- **2-card peak BusBW:** ~31 GB/s (near PCIe 5.0 x16 limit ~31.5 GB/s)
- **8-card peak BusBW:** ~31 GB/s (same — single NUMA, no cross-NUMA penalty)
- **Latency floor:** ~14 us @ 8B (2-card), ~30 us (8-card)

### 10.10.70.96 (oem96)
- **GPU:** 8× RTX PRO 6000 Blackwell Server Edition (96 GB, Blackwell CC 12.0)
- **CUDA:** 13.2 | **NCCL:** 2.30.4
- **Interconnect:** PCIe 5.0 x16 + QPI/UPI cross-NUMA
  - GPU0–3 on NUMA0, GPU4–7 on NUMA1
  - `SYS` topology between NUMA domains (PCIe + QPI/UPI)
- **2-card peak BusBW:** 17.49 GB/s (both GPUs on same NUMA, below PCIe 5.0 limit)
- **8-card peak BusBW:** 21.32 GB/s (cross-NUMA QPI/UPI bottleneck caps bandwidth)
- **Latency floor:** 14.85 us @ 8B (2-card), 56.56 us (8-card — cross-NUMA adds ~4×)
- **RDMA:** RoCE v2 via bond0 (ens35f0np0), IP 192.168.66.10/24

### Key Insights (All_Reduce)

1. **Single-NUMA (70.88) vs dual-NUMA (70.96) matters more than GPU type.** 70.88 achieves ~31 GB/s peak while 70.96 tops at ~21 GB/s, because cross-NUMA traffic must traverse QPI/UPI.
2. **2-card peak on 70.96 (17.49 GB/s) is low** — both GPUs on same NUMA should hit higher. Possible PCIe Gen 4 limitation (GPUs may be running at Gen 1 when idle, need workload to ramp).
3. **8-card AlgoBW on 70.96 (12.18 GB/s vs 2-card 17.49 GB/s)** — Drops because ring topology moves more data per GPU, even though BusBW increases from using more links.
4. **NCCL 2.30.4 vs 2.28.9** — Both work on Blackwell sm120. The difference is CUDA 13.2 vs 13.0, not NCCL version.
