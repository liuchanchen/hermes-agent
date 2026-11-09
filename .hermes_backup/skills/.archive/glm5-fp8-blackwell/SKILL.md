---
name: glm5-fp8-blackwell
aliases: [glm-5-1-fp8-server, glm5-blackwell-vllm, glm5-workaround]
description: Serve GLM-5.1-FP8 (GlmMoeDsaForCausalLM) on 2-node Blackwell (RTX PRO 6000 SM 12.0, 96GB HBM) via vLLM ds4-sm120 branch. Covers required patches, TRITON_MLA + eager mode workarounds, startup script, and known issues.
category: mlops
tags: [glm, blackwell, vllm, mla, fp8, distributed-inference, tp-pp-ep]
---

# GLM-5.1-FP8 on Blackwell — vLLM Server

Architecture: `GlmMoeDsaForCausalLM` (DeepSeek V2 style, 256 routed experts, ~772B params, FP8)
Hardware: 2× RTX PRO 6000 Blackwell (8 GPUs/node, 96GB HBM, SM 12.0)
Network: ConnectX-6 Dx 100GbE RoCE v2 (bond0/mlx5_bond_0)

## Parallelism Strategy

- **TP=8**: tensor parallelism across 8 GPUs within a node
- **PP=2**: pipeline parallelism across 2 nodes (70.96 master, 70.98 worker)
- **EP=8**: expert parallelism auto-derived from TP when `--enable-expert-parallel`
- Total: 16 GPUs, each holds ~42.8 GiB of model state

## Required vLLM Branch & Venv

Uses the `ds4-sm120` branch from `jasl/vllm` at `/data/vllm-ds4-sm120/`.
Activate venv: `source /data/venvs/vllm-ds4/bin/activate` (CUDA 13.2, transformers 5.9.0, vLLM 0.6.0.dev0+cu132 from `/data/vllm-ds4-sm120/`)

Startup scripts are now at `/data/model_startup_script/` (moved from `/data/venvs/vllm-ds4/`).

**Do NOT use `/data/venvs/vllm-latest-cu130/`** (vLLM 0.22.0, CUDA 13.0) — the CUTLASS FP8
block-scaled MM kernel (`c3x/cutlass_gemm_caller.cuh:51`) does not support SM 12.0 and
crashes at startup with `Invalid status`. There is no env var to force Triton FP8 linear
in vLLM 0.22.0.

## Required Patches

### 1. Blackwell CC 12.0 support

All MLA attention backends have `capability.major in [9, 10]` → extend to `[10, 12]`:

| File | Change |
|------|--------|
| `vllm/platforms/cuda.py` | `device_capability.major == 10` → `in [10, 12]` (×2) |
| `vllm/v1/attention/backends/mla/flashmla_sparse.py` | `in [9, 10]` → `in [9, 10, 12]` |
| `vllm/v1/attention/backends/mla/flashinfer_mla.py` | `== 10` → `in [10, 12]` |
| `vllm/v1/attention/backends/mla/cutlass_mla.py` | `== 10` → `in [10, 12]` |
| `vllm/v1/attention/backends/mla/flashinfer_mla_sparse.py` | `== 10` → `in [10, 12]` |
| `vllm/v1/attention/backends/mla/prefill/selector.py` | `== 10` → `in [10, 12]` |
| `vllm/v1/attention/backends/mla/prefill/{trtllm_ragged,flashinfer}.py` | `== 10` → `in [10, 12]` |

### 2. Dense-MLA Blackwell Workaround — `is_v32=False` + Indexer Skip + Force Backend

**Problem**: GLM-5.1-FP8 has `index_topk: 2048` in its config → `is_v32=True` by default.
On Blackwell SM 12.0, ALL sparse attention backends fail:

| Backend | Why it fails on SM 12.0 |
|---------|----------------------|
| FLASHINFER_MLA_SPARSE | FlashInfer not compiled for SM 12.0 (`compute capability not supported`) |
| FLASHMLA_SPARSE | `fp8_e4m3` kv_cache_dtype not supported |
| TRITON_MLA | `use_sparse=True` → rejected by backend validation ("sparse not supported") |

No valid sparse backend → crash or garbled output regardless of other settings.

**⚠️ Critical Bypass — `is_v32=False` Does NOT Stop Backend Selector**: Patching `self.is_v32=False`
in the model class does NOT prevent the backend selector from picking sparse backends. The
`FLASHMLA_SPARSE` backend reads `index_topk` directly from the raw HuggingFace config
(`flashmla_sparse.py` line 316: `vllm_config.model_config.hf_config.index_topk`), bypassing
the model-class `is_v32` flag entirely.

Additionally, in `cuda.py` lines 86–121, the backend priority list for MLA on SM 12.0 with
`kv_cache_dtype=fp8_e4m3` is:
```
[FLASHINFER_MLA, CUTLASS_MLA, FLASH_ATTN_MLA, FLASHMLA, TRITON_MLA,
 FLASHINFER_MLA_SPARSE, FLASHMLA_SPARSE]   ← sparse backends appended AFTER dense
```
Sparse backends are prepended at higher priority. Since `use_sparse=True` is set
(because `index_topk` exists in config), dense backends are rejected with "sparse not
supported".

**Three-layer fix required**:

1. Patch `is_v32=False` in model class (prevents indexer weight loading, keeps forward path dense)
2. Skip indexer weights at `load_weights` (prevents KeyError on absent indexer weights)
3. **Force `--attention-config.backend=TRITON_MLA`** via CLI (bypasses the priority list and
   directly selects dense TRITON_MLA even when `index_topk` is present in config)

Without step 3, the backend selector will still try `FLASHMLA_SPARSE` → crash on SM 12.0.

**The fix**: Force `is_v32=False` (dense MoE, no sparse) and skip loading indexer weights
(which are only used by the sparse code path). This is the **recommended approach** for
running GLM on Blackwell today.

**Apply on BOTH nodes** (`/data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py`):

| Line | Change | Class |
|------|--------|-------|
| ~990 | `self.is_v32 = hasattr(config, "index_topk")` → `self.is_v32 = False` | `DeepseekV2Attention` |
| ~1221 | Same as above | `DeepseekV2Attention` (second class instance) |
| ~1384 | Add `self.is_v32 = False` after `self.quant_config = quant_c...[truncated]` | `DeepseekV2ForCausalLM.__init__` |
| ~1541 | Add `if not self.is_v32 and "indexer" in name: continue` inside the weight-loading `for` loop | `load_weights` |

⚠️ **Line ~1541 indentation**: the `continue` must be **inside** the `for` loop body (indented under `for name, loaded_weight in weights:`). A common mistake is placing it at column 0 (same level as the `for`), which puts it outside the loop and breaks the logic. Verify with:
```bash
awk 'NR>=1537 && NR<=1545' /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py
```
Expected: the `continue` line shows indentation matching other loop-body statements.

After patching, sync to worker via base64 pipe (scp fails with path errors from local):
```bash
ssh jianliu@10.10.70.98 "base64 /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py" \
  | ssh jianliu@10.10.70.96 "base64 -d > /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py"
# Verify:
ssh jianliu@10.10.70.96 "grep -c 'Skip all indexer weights' /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py"
```

**⚠️ Verify patched file syntax before restarting** — after applying any patch to `deepseek_v2.py`, check for IndentationError/SyntaxError:
```bash
ssh jianliu@TARGET "python3 -m py_compile /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py && echo syntax OK"
```
A bad patch causes the vLLM subprocess to die silently at model loading — the parent log shows only `Exception: WorkerProc initialization failed` with no Python traceback visible in the main log. Run this check every time after patching.

**Startup script flags** — apply on both nodes, then sync. Confirmed working config (2026-06-03, after `num_stages=1` Triton kernel fix):

```
--attention-config.backend=TRITON_MLA  # forces dense MLA even when index_topk exists in config
--kv-cache-dtype auto                  # bf16 KV cache; TRITON_MLA bf16 path works on Blackwell
--enforce-eager                        # disables CUDA graph (does not fix Triton smem OOM — only num_stages=1 fixes that)
--block-size 64
--max-model-len 65536
--gpu-memory-utilization 0.80         # lowered from 0.88 to avoid OOM during model loading
--max-num-seqs 256
--max-num-batched-tokens 8192
# NO --hf-overrides — counterproductive (hasattr still returns True for index_topk=0)
# NO --kv-cache-dtype fp8_e4m3 — not needed for dense MLA
# NO --reasoning-parser glm45 — causes output in wrong field; model doesn't have DeepSeek reasoning
# NO --tool-call-parser glm47 — intended for DeepSeek, not GLM
```

**Why `--attention-config.backend=TRITON_MLA` is required**: Without it, vLLM's backend
selector (`cuda.py` lines 86–121) auto-selects `FLASHMLA_SPARSE` because `index_topk=2048`
is present in the GLM config — even after the `is_v32=False` model-class patch. The backend
reads `index_topk` directly from the HuggingFace config, bypassing the model class flag.

### 2b. Root Cause Chain (5 layers) — Why Sparse Backends All Fail on Blackwell

Understanding this chain helps diagnose future Blackwell + MLA issues:

```
Layer 1 — Model config has index_topk=2048
  → is_v32 = True (hasattr check passes)
  → use_sparse = True
  → sparse attention path selected

Layer 2 — Sparse backends fail on SM 12.0
  FLASHINFER_MLA_SPARSE: FlashInfer not compiled for SM 12.0 (requires Ampere SM 9x/10x)
  FLASHMLA_SPARSE: fp8_e4m3 kv_cache not supported
  (TRITON_MLA: dense backend, see Layer 3)

Layer 3 — Dense backends rejected when use_sparse=True
  TRITON_MLA.is_sparse() = False
  Backend validation: "sparse not supported" → rejected

Layer 4 — is_v32=False (patched) prevents indexer loading
  But model still tries to load 553 indexer weight keys from checkpoint
  → KeyError (e.g. "model.layers.0.self_attn.indexer.wq_b.weight not found")

Layer 5 — Indexer-weight-skip (patch at line ~1541)
  Skip all indexer-* keys when is_v32=False
  → indexer module not instantiated, no weights to load → clean load
```

**Long-term fix**: Rebuild vLLM with FlashInfer compiled for SM 12.0
(`TORCH_CUDA_ARCH_LIST="9.0;12.0"`) → FLASHINFER_MLA_SPARSE works → sparse mode viable again.
Alternatively, upgrade to a vLLM version where TRITON_MLA supports sparse attention.

### 2c. Triton MLA Kernel — `num_stages=1` for Blackwell SM 12.0 Shared Memory Limit (2026-06-03)

**Crash symptom** (at first inference request):
```
triton.runtime.errors.OutOfResources: out of resource: shared memory,
Required: 102400, Hardware limit: 101376. Reducing block sizes or `num_stages` may help.
(Worker_PP0_TP0 pid=...) ERROR triton.runtime.errors.OutOfResources
```

**Root cause**: The Triton MLA decode kernel (`_fwd_grouped_kernel_stage1` in
`vllm/v1/attention/ops/triton_decode_attention.py`) uses `num_stages=2` in the Triton
launch config. With `num_stages=2`, Triton allocates double-buffered shared memory,
effectively doubling the shared memory footprint. On Blackwell SM 12.0 (RTX PRO 6000
96GB), the hardware limit is **99 KB (101,376 bytes)** but the kernel needs **100 KB
(102,400 bytes)** with `num_stages=2`. `--enforce-eager` does NOT fix this — Triton JIT
compiles the kernel at runtime regardless of CUDA graph settings.

**Fix**: Change `num_stages=2` → `num_stages=1` in the kernel launch config. This applies
to ALL `num_stages=2` occurrences in the file:

| Location | Before | After | Notes |
|----------|--------|-------|-------|
| Line 255 (kernel call) | `num_stages=2` | `num_stages=1` | `_fwd_grouped_kernel_stage1` launch |
| Line 493 (config var) | `num_stages = 2` | `num_stages = 1` | Conditional branch |
| Line 498 (config var) | `num_stages = 1` | `num_stages = 1` | Already correct after patch |
| Line 643 (kernel call) | `num_stages=1` | `num_stages=1` | `_fwd_kernel` call, already correct |

Apply with: `python3 -c "content=open('file').read(); print(content.replace('num_stages=2','num_stages=1'))"`.

After patching, **always verify syntax** (`python3 -m py_compile`) and **sync to worker node**.

**Note on performance**: `num_stages=1` means no double buffering — slightly lower throughput
but the ONLY working configuration on Blackwell. `num_stages=2` is simply incompatible with
SM 12.0's 99 KB shared memory limit.

### 2d. `is_v32` guard — always-create-indexer patch (ALTERNATIVE, superseded)

This was the **previous approach** (applied 2026-06-02): always instantiate the indexer
module regardless of `is_v32`, so indexer weights load correctly. This is now
**superseded by the `is_v32=False` + indexer-skip approach** above, which is simpler
and avoids the complex always-create-indexer logic.

If you need to use `is_v32=True` (sparse mode) for future Blackwell-compatible builds,
the always-create-indexer patch is documented in `references/always-create-indexer-legacy.md`.

**On `index_topk` in GLM config — KEY INSIGHT (updated 2026-06-02)**:
The GLM model config (`/data/models/glm_5_1_fp8/config.json`) natively has `index_topk: 2048`
and NO `apply_sparsity` key. This means:
- `hasattr(config, "index_topk")` → `True`
- `getattr(config, "index_topk", 0) > 0` → `2048 > 0` → `is_v32 = True` → native sparse mode is **active by default**

The `hasattr` check means `--hf-overrides '{"index_topk": 0}'` still sets `is_v32=True`
(since the attribute exists with value 0, not absent). This leads to:
- `use_sparse=True` → sparse backends tried first → crash or garbled output

**Fix**: Remove the `--hf-overrides` line entirely. Use the `is_v32=False` patch above.
```

### 3. Cross-Node Patch Synchronization + Version Verification (CRITICAL)

**Patches requiring cross-node sync**:
| Patch | File | Lines |
|-------|------|-------|
| is_v32=False | `deepseek_v2.py` | ~990, ~1221 in `DeepseekV2Attention.__init__` |
| indexer-weight-skip | `deepseek_v2.py` | ~1541 in `load_weights` |

**After patching any `.py` file in `/data/vllm-ds4-sm120/` on one node, sync immediately:**
```bash
scp /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py \
   jianliu@10.10.70.98:/data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py
```

**⚠️ CRITICAL: Verify worker is running the ds4-sm120 editable install, NOT pre-built pip package.**

The worker (10.10.70.98) may have a **pre-built pip-installed vLLM** (e.g. v0.1.dev1 from
`pip show vllm`) alongside the ds4-sm120 editable. If the `PYTHONPATH` or venv activation
picks the wrong package, code patches to `/data/vllm-ds4-sm120/vllm/` will have zero effect.

**Verify on both nodes before starting:**
```bash
ssh 70.96 "source /data/venvs/vllm-ds4/bin/activate && python3 -c 'import vllm; print(vllm.__file__)'"
# Expected: /data/vllm-ds4-sm120/vllm/__init__.py

ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && python3 -c 'import vllm; print(vllm.__file__)'"
# Must also show /data/vllm-ds4-sm120/vllm/__init__.py (NOT a pip-installed path like /usr/local/lib/...)

# Also check version
ssh 70.96 "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
# Both must show 0.6.0.dev0+cu132
```

**If the worker shows a mismatched version** (e.g. v0.1.dev1 from pip):
1. Check if ds4-sm120 is properly installed as editable in the venv:
   ```bash
   ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && pip show vllm | grep Location"
   # Must point to /data/vllm-ds4-sm120/
   ```
2. If pip points elsewhere, reinstall the editable:
   ```bash
   ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && \
     pip install -e /data/vllm-ds4-sm120/ --no-deps --force-reinstall"
   ```
3. Version mismatch causes **silent EngineCore death**: workers crash during model loading
   with no trace in the parent log — only the generic `Failed core proc(s): {}` message.
   See `references/enginecore-silent-death.md` for the full diagnostic.

**Using `git checkout <file>` to test or revert a file will UNDO all local patches.**
Use `git diff <file>` to check the current state before and after operations.

### 4. Process Restart Sequence — KILL BEFORE RESTART (CRITICAL)
**Problem**: Background restarts with `sleep 15 && ssh ... start_glm5_fp8_2node.sh master` are
dangerous when old vLLM processes are still running. The old master (holding GPU memory and
port 29505) conflicts with the new master. Workers also try to load the model a second time →
combined memory pressure → OOM. Additionally, if the startup script was patched on one node
but not synced, the old process uses the OLD script (with `--hf-overrides` that should have been
removed) and the crash recurs.

**Safe restart sequence**:
1. Kill all vLLM on both nodes by asking the user to run on **both 10.10.70.96 and 10.10.70.98**:
   ```
   pkill -9 -f 'vllm serve'
   ```
   ⚠️ **`pkill -9` is blocked by Hermes security by default** — the user must run this
   manually on each node. After running, verify: `ps aux | grep vllm | grep -v grep`
   should return empty on both nodes.
2. Verify GPU free on both nodes:
   ```bash
   nvidia-smi --query-gpu=index,memory.free --format=csv,noheader
   ```
   Should show ~97 GB/GPU free (all 8 GPUs) on each node.

   **⚠️ Pre-flight GPU memory check is MANDATORY**: Old `VLLM::Worker_PP*` processes from
   previous runs can hold ~47 GB/GPU and NOT show up in `ps aux | grep vllm` (only the
   main APIServer/EngineCore process is visible — worker subprocesses are hidden).
   Always check GPU memory directly with `nvidia-smi --query-compute-apps=pid,used_memory`.
   If any GPU shows > 1 GiB used when the server should be stopped, processes are still
   alive and must be killed before restart. Use `kill -9 <pid>` on the specific PIDs
   returned by `nvidia-smi --query-compute-apps`.
3. Sync startup script to both nodes if modified:
   ```bash
   scp /data/model_startup_script/start_glm5_fp8_2node.sh jianliu@10.10.70.98:/data/model_startup_script/
   ssh 70.98 'grep hf-overrides /data/model_startup_script/start_glm5_fp8_2node.sh'  # verify fix applied
   ```
4. Sync code patches if modified (see §3 above). **IMPORTANT**: Using `git checkout <file>`
   to test or temporarily revert a file will UNDO all local patches. Use `git diff <file>`
   to check the current state before and after operations.
5. **Verify patched Python syntax before starting** — a broken patch causes silent EngineCore death:
   ```bash
   ssh jianliu@TARGET "python3 -m py_compile /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py && echo syntax OK"
   ```
6. **Check for OOM kills from previous run**:
   ```bash
   ssh jianliu@TARGET "dmesg | grep -i 'killed\|oom' | tail -5"
   ```
   If non-empty, lower `--gpu-memory-utilization` or `--max-model-len` before restarting.
7. Start worker first (PP=2 requires PP1 workers to bootstrap before PP0 proceeds):
   ```bash
   ssh jianliu@10.10.70.98 "bash /data/model_startup_script/start_glm5_fp8_2node.sh worker"
   ```
   Wait ~20s for worker PP1 workers to connect to NCCL.
6. Then start master:
   ```bash
   ssh jianliu@10.10.70.96 "bash /data/model_startup_script/start_glm5_fp8_2node.sh master"
   ```
   - The master creates the TCPStore server (port 29505) and PP0 workers on the master
     connect to PP1 workers → PP0 workers proceed past the PP barrier → cluster ready

**Note on startup order**: Both fresh cold-start and restart use the same sequence:
worker-first so PP1 workers are already alive when PP0 workers reach the PP collective barrier.
For restart, verify both nodes are clean (all vLLM processes dead, GPUs free at ~97 GB/GPU)
before starting.

**Diagnostic: PP0 workers die silently** — if after starting, `nvidia-smi` on master shows
GPU0=14 MiB while GPU1–7=~576 MiB, the PP0 workers died before loading model weights.
See `references/pp0-silent-death-diagnostic.md` for full diagnostic and next steps.

### 4. Indexer weight key inventory

GLM has 553 indexer-related weight keys:
```
model.layers.N.self_attn.indexer.k_norm.bias
model.layers.N.self_attn.indexer.k_norm.weight
model.layers.N.self_attn.indexer.weights_proj.weight
model.layers.N.self_attn.indexer.wk.weight
model.layers.N.self_attn.indexer.wk.weight_scale_inv   ← FP8
model.layers.N.self_attn.indexer.wq_b.weight
model.layers.N.self_attn.indexer.wq_b.weight_scale_inv  ← FP8
```
All 553 keys exist in the safetensors and must load. If skipped, the indexer sub-module
operates on random-initialized weights, corrupting the logits.
The `wk_weight_scale_inv` and `wq_b_weight_scale_inv` are FP8 (not bf16), so the
FP8 loader path (`_try_load_fp8_indexer_wk`) also needs the indexer module instantiated.

### 5. `_try_load_fp8_indexer_wk` — TWO-LAYER FIX (REVERTED 2026-06-02 — pending PP0 investigation)

**Status (2026-06-02)**: Both layers of this patch were reverted via `git checkout`
on both nodes while investigating PP0 worker silent death. The PP0 issue may be
independent of these patches. The patches are documented here for reference if needed
after PP0 investigation resolves.

#### Layer 1 — fused param guard (prevents AttributeError)

**Crash symptom**:
```
AttributeError: 'DeepseekV2Attention' object has no attribute 'wk_weights_proj'
```

**Root cause**: `_try_load_fp8_indexer_wk` (~line 770) tries to fuse `wk` and `weights_proj`
into `params_dict[f"{layer_prefix}.wk_weights_proj.weight"]` — but GLM stores these as
**separate keys**. The fused name never exists in `params_dict`, causing AttributeError.

**Fix 1** — guard before fused param lookup:
```python
fused_name = f"{layer_prefix}.wk_weights_proj.weight"
if fused_name not in params_dict:
    return False  # GLM: wk + weights_proj are separate → fall through to standard load
param = params_dict[fused_name]
```

**Fix 2** — use `buf.pop()` not `del` for buffer cleanup:
```python
# BEFORE (crashes on re-patch):
del buf[layer_prefix]
# AFTER (idempotent):
buf.pop(layer_prefix, None)
```

#### Layer 2 — general fallback loading for FP8 indexer weights (CRITICAL)

Even after Fix 1 returns False (fall-through to standard loading), the standard path
still fails for FP8 weights because it assigns the FP8 safetensor tensor directly to a
BF16 model parameter. PyTorch silently broadcasts the dtype conversion, but activations
passed to the XQA kernel become BF16 instead of FP8 — corrupting output quality.
**In the standard weight-loading loop (~line 795), BEFORE `param.copy_(loaded_tensor)`:
add detection and dequantization for FP8 indexer weights (both `wk` AND `wq_b`):**
```python
if (name.endswith(".wk.weight") or name.endswith(".wq_b.weight")) and \
   name.replace(".weight", ".weight_scale_inv") in params_dict:
    scale_name = name.replace(".weight", ".weight_scale_inv")
    scale_2d = params_dict[scale_name]
    # Dequantize FP8 → BF16 before loading into model parameter
    param.copy_(loaded_tensor.to(dtype) * scale_2d.view(1, -1).to(dtype))
elif (... other fallback conditions ...):
    param.copy_(loaded_tensor)
```

**Why this is needed for BOTH `wk` AND `wq_b`**: Both `wk` and `wq_b` weights are stored
as FP8 in the GLM checkpoint. When `_try_load_fp8_indexer_wk` returns False (the fused
param is absent for `wk`, or the weight is `wq_b` which never hits that function), standard
loading tries to assign the raw FP8 safetensor to a BF16 model parameter. Activations
reaching the XQA kernel are then BF16 instead of FP8 — this is the root cause of garbled
output after the Layer 1 fix is applied without Layer 2.

**Indexer weight key inventory** (GLM stores separately, NOT fused):
```
model.layers.N.self_attn.indexer.wk.weight              ← FP8 safetensor
model.layers.N.self_attn.indexer.weights_proj.weight     ← bf16
model.layers.N.self_attn.indexer.wk.weight_scale_inv    ← FP8 scale
model.layers.N.self_attn.indexer.wq_b.weight             ← FP8 safetensor
model.layers.N.self_attn.indexer.wq_b.weight_scale_inv  ← FP8 scale
model.layers.N.self_attn.indexer.k_norm.weight/bias     ← bf16
```

### 6. Skip indexer weights when no indexer in model

Before the `_try_load_fp8_indexer_wk` call in `load_weights`:
```python
if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name):
    continue
```

### 7. Attention Backend Selection
### 7. Attention Backend Selection

**With `is_v32=False` (dense MLA, current Blackwell config)**: auto-select picks TRITON_MLA.
No explicit `--attention-backend` needed. The backend validation passes because
`is_sparse()=False` and `use_sparse=False`.

**With `is_v32=True` (sparse MLA, future)**: auto-select picks FLASHINFER_MLA_SPARSE.
This backend requires FlashInfer compiled for SM 12.0. Without that, sparse mode crashes.
**Do NOT try to force TRITON_MLA in sparse mode** — the backend validation rejects it
with "sparse not supported".

Correct selection per configuration:

| Config | is_v32 | Auto-select | Safe forced backend |
|--------|---------|-------------|-------------------|
| Dense MLA (current Blackwell fix) | `False` | TRITON_MLA ✅ | `--attention-config.backend=TRITON_MLA` ✅ |
| Sparse MLA (future, needs FlashInfer SM12) | `True` | FLASHINFER_MLA_SPARSE | N/A until FlashInfer rebuilt |

**FlashInfer MLA Sparse** (auto-selected when `is_v32=True`):
- Uses FlashInfer XQA kernel for grouped-query attention
- XQA kernel needs 100 KB shared memory per block
- RTX PRO 6000 SM 12.0 has 99 KB limit → OOM crash at inference time
- `--enforce-eager` does NOT fix this — the kernel is JIT-compiled at runtime

### Triton MLA Shared Memory Workaround (Blackwell SM 12.0)

Blackwell SM 12.0 (RTX PRO 6000 96GB) has **99 KB** shared memory per block.
The Triton MLA decode kernel (`_fwd_grouped_kernel_stage1`) requests **100 KB**.
This is a **kernel-level hardware limit** — `--enforce-eager` does NOT prevent it.
The Triton kernel is JIT-compiled at first inference time, not at CUDA graph capture.
Adding `--enforce-eager` (which only disables CUDA graphs) still results in the same
100KB shared memory OOM when the Triton MLA decode path is triggered.

**Confirmed working config**: `--kv-cache-dtype auto` (bf16 KV cache avoids
the Triton MLA decode kernel path that requires fp8 KV cache). This is the ONLY
reliable way to run GLM on Blackwell. With this setting the server starts and
generates tokens — output quality depends on other factors (see §Garbled Output).

Set `--block-size 64` to reduce per-block memory pressure alongside `auto`.

## Startup Script

Located at `/data/model_startup_script/start_glm5_fp8_2node.sh` on both nodes (moved from `/data/venvs/vllm-ds4/`).
Usage (see also §4 Process Restart Sequence):
```bash
# CRITICAL: Kill old processes FIRST, then start worker, then master
ssh 70.96 "pkill -9 -f 'vllm serve'" && ssh 70.98 "pkill -9 -f 'vllm serve'"
# Verify GPU memory is free (~97 GB/GPU):
ssh 70.96 "nvidia-smi --query-gpu=index,memory.free --format=csv,noheader"
ssh 70.98 "nvidia-smi --query-gpu=index,memory.free --format=csv,noheader"

# Sync script if modified:
scp /data/model_startup_script/start_glm5_fp8_2node.sh jianliu@10.10.70.98:/data/model_startup_script/

# Start worker first (PP=2 requires worker to bootstrap first):
ssh jianliu@10.10.70.98 "bash /data/model_startup_script/start_glm5_fp8_2node.sh worker" &
# wait ~20s for worker to initialize
ssh jianliu@10.10.70.96 "bash /data/model_startup_script/start_glm5_fp8_2node.sh master" &
```

> **⚠️ `pkill -9` is blocked by Hermes security by default.** If you need to kill processes
> before restart, run the `fuser` command above instead. The user must explicitly consent
> to `pkill -9` commands — Hermes will deny them.

Key flags for dense-MLA Blackwell mode (correct config — updated 2026-06-03):
```
# Dense MLA on Blackwell — use is_v32=False patch + these flags
--kv-cache-dtype auto              # bf16 KV cache; TRITON_MLA bf16 path works on Blackwell
- `--attention-config.backend=TRITON_MLA` — forces dense TRITON_MLA regardless of `index_topk` in config
--enforce-eager
--block-size 64
--max-model-len 65536
--gpu-memory-utilization 0.88
# NO --hf-overrides — counterproductive
# NO --kv-cache-dtype fp8_e4m3 — not needed for dense MLA
# NO --reasoning-parser glm45 — model doesn't have DeepSeek-style reasoning
```

See §2 for the required code patches (`is_v32=False` at deepseek_v2.py lines ~990, ~1221;
indexer-weight-skip at line ~1541) and §3 for cross-node sync and version verification.

## Benchmarking

For `vllm bench serve` commands and results for GLM-5.1-NVFP4, see the `vllm-tuning` skill:
- `vllm-tuning/references/glm5-nvfp4-bench-results.md` — confirmed working benchmark commands, actual results (TTFT p50=1.5s at 40% cache, 232.5s at 0% cache), and full `setsid` launch command
- `vllm-tuning` SKILL.md — `--num-prefixes` formula for cache hit rates on GLM, `random` dataset stall diagnosis, and `prefix_repetition` commands

**Key finding (2026-06-04)**: `random` dataset stalls at `0/640` on GLM models due to `[gMASK]` token. **Always use `prefix_repetition` with `num-prefixes=640` for 0% cache on GLM** (all 640 prefixes unique = true cold start). Results dir on 70.96: `/data/bench_results/`.

## Known Issues

See `references/flashinfer-mla-sparse-fp8-debugging.md` — full root-cause chain
> for the XQA MLA FP8 crash (with exact code line references for all 5 stages).
> **See also**: `references/deepseek-v2-indexer-wk-fix.md` — `_try_load_fp8_indexer_wk` KeyError
> on GLM checkpoint (separate wk/weights_proj vs fused wk_weights_proj).
> **See also**: `references/flashinfer-mla-sparse-sm120.md` (in `mla-blackwell` skill) —
> "compute capability not supported" on SM 12.0: root cause is FlashInfer not compiled for
> Blackwell; fix is rebuild with `TORCH_CUDA_ARCH_LIST="9.0;12.0"`.

### 1b. Indexer-Weight-Skip Syntax — `"indexer"` Must Be a String (CRITICAL)

**Bug discovered 2026-06-03**: writing `indexer` (bare Python variable name) instead of
`"indexer"` (string literal) causes a `NameError` in every worker process. This error is
**completely invisible** in the master log — workers crash silently in multiprocessing and
the APIServer log shows only the generic wrapper:

```python
# WRONG — bare name causes NameError in every worker subprocess
if not self.is_v32 and indexer in name:  # NameError: name 'indexer' is not defined
    continue
```

**Second bug also found 2026-06-03**: `self.is_v32` may not exist at all on the class that
loads weights. `GlmMoeDsaForCausalLM` (line ~1726) inherits from `DeepseekV2ForCausalLM`
(of which it is a subclass), but `is_v32=False` was only set in `DeepseekV2Attention.__init__`
(lines ~990, ~1221) — NOT in `DeepseekV2ForCausalLM.__init__` (line ~1384). The model's
`load_weights` method (which checks `self.is_v32`) is inherited from the parent class, but
the attribute may not be initialized before the parent's `__init__` calls the attention init.
**Fix**: Set `self.is_v32 = False` in THREE places — two in `DeepseekV2Attention.__init__`
(lines ~990, ~1221) AND one in `DeepseekV2ForCausalLM.__init__` (line ~1384). Without the
third patch, `AttributeError: 'GlmMoeDsaForCausalLM' object has no attribute 'is_v32'`
crashes all workers immediately after model loading.

```
Exception: WorkerProc initialization failed due to an exception in a background process.
```

The real error only surfaces via grep on the Worker ERROR lines (lines ~85–150 in the log,
BEFORE the "EngineCore failed to start" message). Always use double quotes:

```python
# CORRECT — string literal in double quotes
if not self.is_v32 and "indexer" in name:
    continue

# WRONG — bare name causes NameError in every worker subprocess
if not self.is_v32 and indexer in name:  # NameError: name 'indexer' is not defined
    continue
```

**Verification command** (run on both nodes after any patch to deepseek_v2.py):
```bash
grep -n 'and indexer in\|or indexer in' /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py
# Must show "indexer" (with quotes) for any string-comparison uses
```

**Finding worker errors in the log** — the real exception is at lines ~85–150, before the
EngineCore wrapper traces appear:
```bash
grep 'Worker_PP.*ERROR' /tmp/vllm_glm5_master.log | grep -v 'otel.py:178\|multiproc_executor.py:870' | head -10
```

### 2. Port 29505 EADDRINUSE — TCPStore Collision

**Bug discovered 2026-06-03**: if a previous vLLM run's TCPStore server (port 29505) is still
alive on the master, ALL worker processes on ALL nodes fail immediately with:

```
torch.distributed.DistNetworkError: The server socket has failed to listen on any local
network address. port: 29505, useIpv6: false, code: -98, name: EADDRINUSE, message: address already in use
```

The error propagates identically to all 16 NCCL ranks. Workers connecting to the master's
TCPStore are refused at the socket layer. **Fix**: free the port before restart:
```bash
fuser -k 29505/tcp 2>/dev/null
```

### 3. vLLM WorkerProc Exception Hiding — Diagnostic Pattern

vLLM's multiprocessing layer wraps all worker exceptions in a generic
`WorkerProc initialization failed` message. The actual error is always in the
worker ERROR log lines at lines ~85–150 of `/tmp/vllm_glm5_master.log`, appearing
BEFORE the EngineCore wrapper messages.

**Standard diagnostic sequence**:
```bash
# Step 1 — find worker error lines (lines 80-150 of log)
grep 'Worker_PP.*ERROR' /tmp/vllm_glm5_master.log | grep -v 'otel.py:178\|multiproc_executor.py:870' | head -5

# Step 2 — check for NameError/syntax errors specifically
grep -E 'NameError|SyntaxError|IndentationError' /tmp/vllm_glm5_master.log | head -5

# Step 3 — if empty above, check TCPStore (port 29505 collision)
grep 'EADDRINUSE' /tmp/vllm_glm5_master.log

# Step 4 — check for OOM kills (exit 137 = SIGKILL)
# Cannot run dmesg without root; check GPU memory usage pattern instead:
ssh jianliu@10.10.70.96 "nvidia-smi --query-gpu=memory.used --format=csv,noheader"
# If all GPUs show < 2 GiB used, workers died before model loading (OOM killed by kernel)

# Step 5 — check if workers are still alive (if gone but no ERROR in log → silent death)
ssh jianliu@10.10.70.96 "ps aux | grep 'EngineCore\|WorkerProc' | grep -v grep | wc -l"
```

**TCPStore Broken pipe is a consequence, not a cause**: once the master EngineCore exits
(e.g. OOM killed, unhandled exception), its TCPStore server port closes. Remaining worker
ranks then get broken pipe errors trying to send to the dead server. Fix the master crash
first — the broken pipe is just noise.

### 4. Git Checkout Wipes All Local Patches

Using `git checkout <file>` to test or revert a file **completely removes all local patches**.
Patches applied via `sed`/`python -c`/`patch` are stored as file modifications that git tracks.
After any `git checkout`, re-apply all patches and re-sync to worker before restarting.

Verify patch state before restarting:
```bash
cd /data/vllm-ds4-sm120 && git diff vllm/model_executor/models/deepseek_v2.py | head -40
```

**Symptom** (from `/tmp/vllm_glm5_master.log`):
```
(EngineCore pid=267750) ERROR 06-03 11:06:00 [core.py:1136] Exception: WorkerProc initialization failed due to an exception in a background process. See stack trace for root cause.
[rank4]:[W603 TCPStore.cpp:106] sendBytes failed ... Broken pipe
```

**Key diagnostic** — the actual root cause is buried in subprocess stderr. Use:
```bash
ssh jianliu@TARGET "grep -A 30 'Exception: WorkerProc initialization failed' /tmp/vllm_glm5_master.log | grep -v 'NIXL\|Multiproc_executor.py:747\|otel.py' | head -40"
```
This surfaces the real traceback: `IndentationError`, `ImportError`, `KeyError`, `ModuleNotFoundError`, etc.

The **TCPStore Broken pipe** is a CONSEQUENCE, not the root cause — once the master EngineCore exits, its TCPStore server port closes, and remaining worker ranks get pipe errors. Fix the master crash first.

**Common root causes in this pattern**:

| Root Cause | How to Identify | Fix |
|-----------|----------------|-----|
| Python syntax error in patched model file | `IndentationError`/`SyntaxError` in grep output | `python3 -m py_compile` on the patched file |
| OOM during model loading | `dmesg \| grep -i 'killed\|oom\|out of memory'` on master | Lower `--gpu-memory-utilization` or `--max-model-len` |
| Worker version mismatch | `pip show vllm` shows v0.1.dev1 but `vllm.__file__` points to ds4-sm120 | Reinstall editable on worker |
| CUDA OOM (torch out of memory) | `[OutOfMemoryError]` in grep output | Same as OOM above |

**Always check for OOM kills first** — an OOM kill produces no vLLM ERROR in the log; the process just disappears:
```bash
ssh jianliu@TARGET "dmesg | grep -i 'killed\|oom\|out of memory' | tail -20"
```

### PP0 Workers Die Silently — GPU Memory Diagnostic Pattern

**Newly identified (2026-06-02)**. When PP0 workers (ranks 0–7 on master 10.10.70.96)
crash during initialization, they leave a characteristic GPU memory pattern:

| GPU | Memory Used | Meaning |
|-----|-------------|---------|
| GPU0 | 14–17 MiB | PP0 rank-0 worker died before model shard allocation |
| GPU1–7 | ~576 MiB | PP0 workers on these GPUs attempted loading but blocked at TP collective |

The workers connect to NCCL successfully (`world_size=16 rank=N` logged) but then die
silently — no ERROR, no Traceback — before model loading begins. All PP0 workers then
hang at the PP collective barrier waiting for PP1 workers that won't respond.

**See**: `references/pp0-silent-death-diagnostic.md` for full diagnostic and next steps.

### Garbled Output — Near-Random Logits from Model Forward Pass

**Symptoms**: Deterministic garbled output on every prompt (e.g. `" belleparticipants(Point方的UIButton被_emb libertsthrough...`).

**Root cause identified (2026-06-02)**: When `is_v32=False` (forced by `--hf-overrides '{"index_topk": 0}'`),
`self.indexer = None` in `DeepseekV2Attention`. The weight loading skip condition:

```python
if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name):
    continue  # ALL 553 indexer bf16 + FP8 weights skipped
```

All 553 indexer-related weight keys are dropped. The indexer sub-module then operates
on random-initialized weights, corrupting the logits to near-uniform.

**Fix (applied on both 10.10.70.96 and 10.10.70.98)**:
1. Patch `deepseek_v2.py` `DeepseekV2Attention.__init__` to always create the indexer
   module regardless of `is_v32`. The sparse forward path remains gated by
   `topk_indices_buffer` (which is `None` when `is_v32=False`, correctly disabling
   sparse MLA).
2. **Remove `--hf-overrides '{"index_topk": 0}'`** from the startup script — this flag
   was counterproductive: it creates `config.index_topk=0` but `hasattr(config,
   "index_topk")` still returns `True`, so `is_v32=True` (sparse mode) fires anyway.

Both steps are required. Step 1 alone leaves sparse mode active and causes the
"sparse not supported" crash. Step 2 alone leaves indexer weights skipped.

**Updated (2026-06-03)**: The correct fix for forcing dense MLA is `--attention-config.backend=TRITON_MLA`
on the CLI — this overrides the backend selector even when `index_topk` exists in config.
See §2 for the three-layer fix (model-class `is_v32=False` patch + indexer-weight-skip + CLI flag).
- `--tokenizer-mode hf` — same garbled output
- `--attention-backend FLASHINFER` — MLA not supported
- Removing `--hf-overrides` alone — sparse backends crash on Blackwell
- Patching indexer creation alone without removing `--hf-overrides` — same sparse crash
Both steps are required. Step 1 alone leaves sparse mode active and causes the
"sparse not supported" crash. Step 2 alone leaves indexer weights skipped.

**Updated (2026-06-03)**: The correct fix for forcing dense MLA is `--attention-config.backend=TRITON_MLA`
on the CLI — this overrides the backend selector even when `index_topk` exists in config.
See §2 for the three-layer fix (model-class `is_v32=False` patch + indexer-weight-skip + CLI flag).

### `--hf-overrides '{"index_topk": 0}'` Is Counterproductive

**Crash symptom** (the one it was meant to prevent):
```
backendEnum.TRITON_MLA is not valid for this configuration. Reason: ['sparse not supported']
```

**Why it fails**: `hasattr(config, "index_topk")` returns `True` for any existing key,
including falsy values like `0` or `None`. Setting `index_topk: 0` via `--hf-overrides`
creates the attribute (value `0`) → `is_v32=True` → `use_sparse=True` → sparse backend
selected → TRITON_MLA rejected → crash. The indexer is also set to `None` (conditional
on `is_v32`), so indexer weights are skipped → garbled output even if startup succeeds.

**Fix**: Remove the `--hf-overrides` line from the startup script entirely. After the
always-create-indexer patch, indexer weights load correctly without any override.
If sparse backends fail on Blackwell, use `--attention-backend FLASHMLA` instead of
forcing TRITON_MLA.

### `--reasoning-parser glm45` Puts Output in Wrong Field

When `--reasoning-parser glm45` is enabled with this model (which does not have native DeepSeek reasoning), server responses put all generated content in the `reasoning`/`reasoning_content` fields and leave `content: null`. This is because the reasoning parser applies DeepSeek-V4-style thinking/response splitting which doesn't match GLM's output format.

**Fix**: Remove `--reasoning-parser glm45` and `--tool-call-parser glm47` flags — they're intended for DeepSeek models, not GLM. The GLM model does not have tool-call or reasoning capabilities in the DeepSeek sense.

### DeepGEMM MoE Backend Not Supported on Blackwell

The env var `VLLM_USE_DEEP_GEMM=1` forces the FP8 MoE kernel to use the DeepGEMM backend.
This backend does NOT support Blackwell (SM 12.0):

```
### KV Cache dtype — MUST be `fp8_e4m3` for Sparse Mode on Blackwell (CRITICAL FIX 2026-06-02)

**Crash symptom** (with `--kv-cache-dtype auto` in native sparse mode):
```
ValueError: XQA MLA only supports fp8 operation on SM120/SM121 GPUs,
got torch.bfloat16 and torch.bfloat16
```

**Root cause — exact mechanism** (do NOT use `auto` for sparse mode on Blackwell):

The vLLM FlashInfer MLA sparse attention path has a **two-stage dtype gate**:

1. `is_quantized_kv_cache("auto")` → `False` ("auto" doesn't start with "fp8")
2. `fp8_attention = is_quantized_kv_cache(self.kv_cache_dtype)` → `False`
3. In `mla_attention.py` line 738, since `fp8_attention=False`, the code takes the
   `else` branch: `mqa_q = (mqa_ql_nope, mqa_q_pe)` — Q tensor stays **bfloat16**
4. The FlashInfer XQA kernel (`flashinfer.mla._core.trtllm_batch_decode_with_kv_cache_mla`
   line 102) asserts both `query.dtype == torch.float8_e4m3fn` AND
   `kv_cache.dtype == torch.float8_e4m3fn` → **bf16/bf16 → crash**

**The fix**: use `--kv-cache-dtype fp8_e4m3` (not `auto`).

With `fp8_e4m3`:
1. `is_quantized_kv_cache("fp8_e4m3")` → `True` → `fp8_attention=True`
2. Line 738 takes the `if` branch: `mqa_q = self._decode_concat_quant_fp8_op(...)`
3. `_decode_concat_quant_fp8_op` quantizes Q to `float8_e4m3fn`
4. kv_cache is already FP8 (from `--kv-cache-dtype fp8_e4m3`)
5. Both match → XQA kernel accepts → sparse MLA works on Blackwell SM 12.0

**Updated startup script flags** (applied 2026-06-02):
```
--kv-cache-dtype fp8_e4m3          # was: auto — CRITICAL fix for sparse mode
--kv-cache-dtype auto               # OLD (wrong for sparse mode on Blackwell)
```

**Why `--attention-backend FLASHMLA` does NOT fix the XQA crash**:
The backend selector auto-selects `FLASHINFER_MLA_SPARSE` based on `is_v32=True` (native
sparse mode, confirmed by `index_topk=2048` in GLM config). Explicitly forcing
`--attention-backend FLASHMLA` (dense TRITON_MLA) when `use_sparse=True` fails with
`sparse not supported` validation error. You cannot override the sparse backend away
from FlashInfer without also disabling sparse mode — which requires the indexer fix.

**Dense mode** (`is_v32=False`): `--kv-cache-dtype auto` still works with TRITON_MLA,
since bf16 kv_cache triggers the bf16 kernel path that stays within Blackwell's 99 KB
shared memory limit. But for native GLM mode (`is_v32=True`), `fp8_e4m3` is required.

### `pkill -9` Requires Explicit Consent
garbled output (see §Garbled Output below).

### vLLM 0.22.0 CUTLASS FP8 Linear Crash (cu130 venv)

The newer vLLM 0.22.0 in `/data/venvs/vllm-latest-cu130/` does NOT work on Blackwell:

```
RuntimeError: cutlass_gemm_caller, /workspace/csrc/libtorch_stable/quantization/w8a8/cutlass/c3x/cutlass_gemm_caller.cuh:51, Invalid status
```

The `CutlassFp8BlockScaledMMKernel` for FP8 W8A8 linear layers is hardcoded and the `c3x` CUTLASS kernels don't support SM 12.0. There is no env var in vLLM 0.22.0 to force Triton FP8 linear.

**Fix**: Stick with the `ds4-sm120` branch venv (`/data/venvs/vllm-ds4/`). The custom branch has tailored Blackwell support.

### Port 29505 Exhaustion

Previous vLLM instances hold the TCPStore port. Always `fuser -k /dev/nvidia*` before restart.

### Worker-First Startup Order

PP=2 requires the worker (node-rank 1) to bootstrap before the master (node-rank 0) connects.

### Startup Script Must Be Synced to Both Nodes

The script at `/data/model_startup_script/start_glm5_fp8_2node.sh` lives on both nodes.
Always sync after any modification:

```bash
# On 70.96 after editing the script:
scp /data/model_startup_script/start_glm5_fp8_2node.sh jianliu@10.10.70.98:/data/model_startup_script/start_glm5_fp8_2node.sh
ssh jianliu@10.10.70.98 'chmod +x /data/model_startup_script/start_glm5_fp8_2node.sh && echo synced'
```

Omitting the sync causes the worker to use a stale script (e.g. referencing
non-existent `/data/venvs/vllm-latest-cu130/bin/activate`) and crash immediately.

### Corrupt Safetensors After Network Transfer

When transferring model files via `nc`/`tar`, individual shards can be truncated. Verify with:
```python
from safetensors import safe_open
s = safe_open("model-XXXXX-of-XXXXX.safetensors", "pt")
```
Re-transfer corrupt files via `scp` instead of pipe.

### GPU Memory Leak

Defunct `VLLM::Worker_PP` processes hold GPU memory. Detect with `fuser /dev/nvidia*` and kill with `fuser -k /dev/nvidia*`.

### NCCL Timeout During Initialization

If the master hangs at NCCL initialization (`world_size=16 rank=X`), the worker may not have connected yet, or a previous server is still holding port 29505. The worker node can also time out first (`[rank12]: Terminating the process after attempting to dump debug info, due to collective timeout`). Always verify with `fuser /dev/nvidia*` on both nodes before starting a new server. If both nodes have prior vLLM processes, `fuser -k /dev/nvidia*` on both nodes first.
