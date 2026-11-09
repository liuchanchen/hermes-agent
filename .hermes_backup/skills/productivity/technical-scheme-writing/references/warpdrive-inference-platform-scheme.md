# Heterogeneous inference platform scheme — session specifics (2026-08)

Concrete template instance of the class. Reuse/adapt for future WarpDrive
inference-platform 方案.

## Deliverable structure that worked (chapters 1–7)
1. 方案背景与目标 (performance/cost/supply-chain goals + 5 design principles)
2. 硬件选型与算力配比 (card-family table + ratio 1:1)
3. 系统总体架构 (client → API gateway → scheduler → pools → RDMA switch)
4. 调度器设计（WarpDrive Smart Scheduler）— keep algorithm INTERNAL ("不展开"),
   only goals + routing policy + elasticity
5. 服务器与网络布局 (H200/B300 vs TGU pool nodes, RDMA switch, plane table)
6. 关键流程 (request lifecycle, cross-pool RDMA cooperation)
7. 关键指标与验证 (TTFT/TPOT/goodput/pool-utilization/domestic-utilization)

## Card specs (user-provided ground truth, 2026-08)
曲速(WarpDrive) TGU family FP16 稠密算力 vs B300(=2250T baseline):
- TGU02-F 500T (1:4.5), TGU01-F 250T (1:9, INT8 500 TOPS/card,
  the mainstream pick), TGU02-H2 200T (1:11), TGU02-H 100T (1:22)
- vs H200 ≈989T: approx 1:2 / 1:4 / 1:5 / 1:10 respectively
- Non-domestic: B300 (Blackwell Ultra) 2250T baseline, 288GB HBM3e ~8TB/s
  (derived from NVIDIA GB300 NVL72 rack datasheet: 72 GPUs, 20TB mem / 576TB/s /
  130TB/s NVLink; per-GPU ≈ /72); H200 SXM 141GB HBM3e 4.8TB/s ≈989T

## Compute-ratio derivation pattern (print the arithmetic)
- 1 H200 ≈989T ⇒ ≈4×TGU01-F(250), 2×TGU02-F(500), 5×TGU02-H2(200), 10×TGU02-H(100)
- 1 B300 2250T ⇒ 9×TGU01-F, 4.5×TGU02-F, 11×TGU02-H2, 22.5×TGU02-H
- 1:1 total: e.g. 1 node×8×H200 ≈8000T vs 4 nodes×8×TGU01-F(32) = 8000T / 16k TOPS

## Files in /home/jianliu/tgu01f-h200-platform/
- 方案_基于曲速自研算力卡与非国产算例卡的异构大模型推理平台方案_v1.2.md (source)
- 方案_…非国产算力卡….docx (final Word deliverable; 章节1-7, 4 tables, 2 embedded PNGs)
- diag1.html / diag2.html (diagram sources; chrome-rendered to diagram_1/2.png)
- compute_power_ratio.md (the user-extracted card-family table — when the agent
  can't OCR an image, ask the user to extract it to a text/md file instead of
  installing OCR tools)

## Notes
- EcoServe / distributed-LLM-serving theory became "WarpDrive Smart Scheduler"
  per user instruction — scheduler internals not exposed in the 方案.
- Title rebrand is a frequent user step (card codename → product name,
  nationality phrasing); sweep body headings too.
