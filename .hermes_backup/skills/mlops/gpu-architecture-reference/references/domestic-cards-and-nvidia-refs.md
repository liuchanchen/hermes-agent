# 国产算力卡 (Domestic Accelerators) + NVIDIA Datasheet References

Session-derived hardware reference for heterogeneous LLM inference-cluster design.
Complements the umbrella SKILL.md (which covers Huawei Ascend + interconnect).
Date captured: 2026-08-10.

## 曲速 (WarpDrive) TGU 系列 — self-developed domestic accelerator cards

FP16-dense compute relative to B300 (NVIDIA Blackwell Ultra, the scheme's ratio baseline).

| Card | FP16 dense (T/card) | vs B300 | vs H200 (~989T) |
|------|--------------------|---------|-----------------|
| B300 (non-domestic ref) | 2250 | — | ≈1:2.3 |
| H200 SXM | ≈989 | ≈1:2.3 | — |
| TGU02-F | 500 | 1:4.5 | 1:2 |
| TGU01-F | 250 (INT8 500T/card, 2:1) | 1:9 | 1:4 |
| TGU02-H2 | 200 | 1:11 | 1:5 |
| TGU02-H | 100 | 1:22 | 1:10 |

Conversion rule: 1 H200 ≈ 4× TGU01-F ≈ 2× TGU02-F ≈ 5× TGU02-H2 ≈ 10× TGU02-H.
1 B300 ≈ 9× TGU01-F etc. (i.e. the ratio table above).

## B300 / GB300 (NVIDIA Blackwell Ultra) — official datasheet values

Source: NVIDIA GB300 NVL72 official datasheet (nvidia.com/en-us/data-center/gb300-nvl72/).
Rack = 72 Blackwell Ultra GPUs + 36 Grace CPUs.

| Item (rack-level) | Value |
|-------------------|-------|
| GPU memory | 20 TB (÷72 ≈ **288 GB HBM3e/card**) |
| Memory bandwidth | up to 576 TB/s (÷72 ≈ **8 TB/s/card**) |
| NVLink bandwidth | 130 TB/s |
| Fast memory | 37 TB |
| FP16/BF16 Tensor Core | 360 PFLOPS (with sparsity) → per-card ~5 PFLOPS sparse / ~2.5 PFLOPS dense (=2500 T) |

Note: official per-card dense ≈2500 T vs the scheme's 2250 T baseline differ by ~10% — decide one canonical baseline and document both.

## H200 SXM (NVIDIA Hopper) — official values

Per NVIDIA H200 product page: 141 GB HBM3e, 4.8 TB/s, ≈989 TFLOPS FP16/BF16 dense.

## Heterogeneous serving scheduler reference — EcoServe

Paper: "EcoServe: Enabling Cost-effective LLM Serving with Proactive Intra- and Inter-Instance
Orchestration", arXiv:2504.18154 (Sun Yat-sen Univ., 2025). This is the paper behind the
"Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration"
title (non-exact echo). It is a partially-disaggregated (PaDG) serving system:
- three-level scheduling: overall → macro-instance → instance scheduler;
- temporal disaggregation of prefill/decode within an instance + rolling activation across instances;
- adaptive scheduling (Inter-Instance round-robin, CheckConstraints on TTFT/saved-TPOT/KV capacity, Intra-Instance prefill-first);
- Mitosis scaling for elastic per-instance capacity.

Good pattern library for building a heterogeneous (domestic + non-domestic GPU) inference platform
with an RDMA fabric and a pre-GPU routing scheduler.
