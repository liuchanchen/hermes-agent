---
name: cutlass-tensorcore-benchmark
description: Run CUTLASS Tensor Core GEMM benchmarks.
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [CUTLASS, Benchmark, GPU, CUDA, TensorCore]
---

# CUTLASS Tensor Core Benchmark Workflow

End-to-end CUTLASS profiler deployment and Tensor Core GEMM benchmarking. Three scripts work together: a main workflow script that auto-detects an existing `cutlass_profiler`, optionally deploys one from source, and runs benchmarks across specified GPU devices and precision formats. Already validated on the TGU01-Pro cluster (68.96 / 68.88) through both "reuse existing profiler" and "first-time auto-deploy" paths.

**What this does NOT cover:** NCCL bandwidth tests, vLLM throughput benchmarks, or general GPU diagnosticsheb.

## When to Use

- "Benchmark CUTLASS Tensor Core performance"
- "Run CUTLASS profiler on 68.96"
- "Measure GEMM throughput for sm120/Blackwell"
- "Compare f16/bf16/tf32/fp8/nvfp4/mxfp4 GEMM kernels"
- "Deploy CUTLASS profiler from source"

## Prerequisites

- **Scripts** on the target server at `~/work/tgu01-pro-model-deployment/gpu_performance_test/cutlass_profiler/`:
  - `run_cutlass_tensorcore_workflow.sh` — orchestrator
  - `deploy_cutlass_profiler.sh` — builds and installs `cutlass_profiler`
  - `benchmark_cutlass_tensorcores.sh` — runs kernels on selected devices
- **Dependencies** (installed by deploy script): CUDA toolkit, ninja-build, git
- **Server**: 68.96 (proxy in `.bashrc`) or any GPU server in the 10.10.68.x cluster. For no-proxy servers (68.92, 68.98), the deploy script's git clone to GitHub needs HTTP_PROXY configured.
- **Profiler search order** (built into workflow script):
  1. `--profiler PATH` argument
  2. `CUTLASS_PROFILER` environment variable
  3. `cutlass_profiler` on `PATH`
  4. Auto-generated path from `--prefix` (default: `$HOME/opt/cutlass-profiler-sm120/bin/cutlass_profiler`)

## How to Run

Invoke through the `terminal` tool on the target server:

```bash
cd ~/work/tgu01-pro-model-deployment/gpu_performance_test/cutlass_profiler

# Single GPU quick test
bash run_cutlass_tensorcore_workflow.sh --devices 0 --quick

# 8-GPU stable test with all precisions
bash run_cutlass_tensorcore_workflow.sh \
  --devices 0-7 \
  --precisions f16,bf16,tf32,fp8,nvfp4,mxfp4 \
  --stable

# Force redeploy with extended kernel set
bash run_cutlass_tensorcore_workflow.sh \
  --force-deploy \
  --kernel-set extended \
  --jobs 16 \
  --devices 0 \
  --stable
```

## Quick Reference

| Script | Lines | Purpose |
|--------|-------|---------|
| `run_cutlass_tensorcore_workflow.sh` | 284 | Orchestrator: discover or deploy profiler, then benchmark |
| `deploy_cutlass_profiler.sh` | 250 | Clone CUTLASS, build `cutlass_profiler` for sm120/Blackwell |
| `benchmark_cutlass_tensorcores.sh` | 483 | Run GEMM benchmarks across device(s) and precision formats |

**Workflow flags:**
| Flag | Description |
|------|-------------|
| `--profiler PATH` | Use existing profiler binary |
| `--force-deploy` | Rebuild even if valid profiler exists |
| `--skip-deploy` | Fail if no valid profiler exists |
| `--deploy-script PATH` | Custom deploy script path |
| `--benchmark-script PATH` | Custom benchmark script path |
| `--prefix PATH` | Deployment prefix (default: `$HOME/opt/cutlass-profiler-sm120`) |
| `--cutlass-ref REF` | CUTLASS branch/tag/commit to build |

**Benchmark flags (passed through workflow):**
| Flag | Description |
|------|-------------|
| `--devices SPEC` | GPU indexes: `0`, `0-7`, `0,2,4`, or `all` |
| `--precisions LIST` | Comma-sep: `f16,bf16,tf32,fp8,nvfp4,mxfp4` |
| `--quick` | Brief smoke-test suite |
| `--stable` | Extended stable benchmark suite |
| `--parallel` | Run devices in parallel (multi-GPU) |
| `--output-dir PATH` | Results directory (default: `./results/`) |
| `--kernel-set KIT` | `default` or `extended` (includes NVFP4/MXFP4) |
| `--jobs N` | Parallel compilation jobs (default: `nproc`) |

## Procedure

### 1. Quick smoke test (single GPU, default precision)

```bash
cd ~/work/tgu01-pro-model-deployment/gpu_performance_test/cutlass_profiler
chmod +x *.sh
bash run_cutlass_tensorcore_workflow.sh --devices 0 --quick
```

The workflow auto-detects if a `cutlass_profiler` exists (checking `PATH`, `CUTLASS_PROFILER` env var, and the default install path). If found, it prints `Existing CUTLASS Profiler detected — Deployment skipped` and proceeds directly to benchmarking. If not found, it runs `deploy_cutlass_profiler.sh` first.

### 2. Full 8-GPU stable benchmark

```bash
bash run_cutlass_tensorcore_workflow.sh \
  --devices 0-7 \
  --precisions f16,bf16,tf32,fp8,nvfp4,mxfp4 \
  --stable \
  --parallel
```

### 3. Force redeploy with extended kernels (NVFP4/MXFP4)

If the profiler lacks NVFP4 or MXFP4 kernels, force a rebuild:

```bash
bash run_cutlass_tensorcore_workflow.sh \
  --force-deploy \
  --kernel-set extended \
  --jobs 16 \
  --devices 0-7 \
  --stable
```

### 4. Custom profiler path

```bash
bash run_cutlass_tensorcore_workflow.sh \
  --profiler /custom/path/cutlass_profiler \
  --devices 0 \
  --quick
```

## Pitfalls

- **Proxy required on 68.96/68.88/68.95**: The deploy script clones CUTLASS from GitHub. On proxy servers, `source ~/.bashrc &&` must be sourced first to set `HTTP_PROXY`. The workflow and deploy scripts should handle this if `~/.bashrc` has the proxy, but non-interactive SSH may skip it — run manually or ensure `HTTP_PROXY` is set.
- **`--quick` vs `--stable`**: Quick runs only a small subset of problem sizes and precisions for pass/fail validation. Stable runs the full suite — budget 30-60 min per GPU for stable mode.
- **`--parallel` launches benchmarks simultaneously on all specified GPUs**: Useful for multi-GPU nodes but results will interleave in log output. Omit `--parallel` for sequential runs on each GPU.
- **Default precision list**: When `--precisions` is omitted, the benchmark script uses its own defaults (typically `f16,bf16,tf32`). Pass `--precisions f16,bf16,tf32,fp8,nvfp4,mxfp4` explicitly to get NVFP4/MXFP4 results.
- **Extended kernel set**: NVFP4 and MXFP4 kernels may not be in the default build. Use `--force-deploy --kernel-set extended --jobs 16` to compile them. This takes significantly longer.
- **Results directory**: Default is `./results/` relative to the working directory. Check `--output-dir` to customize.

## Verification

Run the quick smoke test on any single GPU:

```bash
cd ~/work/tgu01-pro-model-deployment/gpu_performance_test/cutlass_profiler
bash run_cutlass_tensorcore_workflow.sh --devices 0 --quick 2>&1 | tail -10
```

When a valid profiler exists, expect output containing `Existing CUTLASS Profiler detected` followed by GEMM throughput results (TFLOP/s values).
