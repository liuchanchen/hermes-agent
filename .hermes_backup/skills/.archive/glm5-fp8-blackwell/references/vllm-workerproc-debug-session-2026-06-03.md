# GLM-5.1-FP8 vLLM Debugging — Session 2026-06-03

## Bug 1: NameError in Indexer Weight Skip (Root Cause of "WorkerProc Init Failed")

**File**: `vllm/model_executor/models/deepseek_v2.py`, line ~1558
**Symptom**: All 8 master worker processes exit silently. Log shows generic `WorkerProc initialization failed`.
**Actual error** (found via grep of worker ERROR lines):
```
NameError: name 'indexer' is not defined
  File "...deepseek_v2.py", line 1558
    if not self.is_v32 and indexer in name:
```
**Cause**: Written `indexer` (bare variable) instead of `"indexer"` (string literal).
Python checks variable `indexer` → not defined → NameError in every subprocess.

**Fix**:
```python
# CORRECT
if not self.is_v32 and "indexer" in name:
    continue
```

**How to find**: grep for worker ERROR lines at lines ~85-150 (NOT the EngineCore wrapper at lines 200+):
```bash
grep 'Worker_PP.*ERROR' /tmp/vllm_glm5_master.log | grep -v 'otel.py:178\|multiproc_executor.py:870' | head -5
```

## Bug 2: Port 29505 EADDRINUSE (TCPStore Collision)

**Symptom**: All 16 NCCL ranks fail immediately with EADDRINUSE on port 29505.
**Cause**: Previous vLLM master process still holding TCPStore port.
**Fix**: `fuser -k 29505/tcp` before restart.

## Bug 3: TRITON_MLA + Enforce-Eager Removed

Removed both `--attention-config.backend=TRITON_MLA` and `--enforce-eager` flags during
testing (2026-06-03). This changed the backend selection from forcing dense TRITON_MLA
to auto-select. The auto-select path with `--kv-cache-dtype auto` may pick a different
backend. If startup fails, re-add these flags.

## Indexer Weight Keys in GLM Checkpoint

```
model.layers.N.self_attn.indexer.k_norm.weight       ← bf16
model.layers.N.self_attn.indexer.k_norm.bias       ← bf16
model.layers.N.self_attn.indexer.weights_proj.weight ← bf16
model.layers.N.self_attn.indexer.wk.weight           ← FP8
model.layers.N.self_attn.indexer.wk.weight_scale_inv ← FP8 scale
model.layers.N.self_attn.indexer.wq_b.weight         ← FP8
model.layers.N.self_attn.indexer.wq_b.weight_scale_inv ← FP8 scale
```

All of these exist in the checkpoint (verified via safetensors header parsing).
With `is_v32=False`, all are skipped via the `"indexer" in name` continue guard.

## Startup Script Final Config (2026-06-03)

```bash
--gpu-memory-utilization 0.80   # reduced from 0.88
--kv-cache-dtype auto
--max-model-len 65536
# TRITON_MLA flags removed for testing
# --attention-config.backend=TRITON_MLA  ← temporarily removed
# --enforce-eager                       ← temporarily removed
```

## Log Analysis Sequence

When troubleshooting "WorkerProc initialization failed":
1. `grep 'Worker_PP.*ERROR' /tmp/vllm_glm5_master.log | head -5` — find worker error lines (~85-150)
2. `grep -E 'NameError|SyntaxError|KeyError' /tmp/vllm_glm5_master.log | head -5` — specific Python errors
3. `grep 'EADDRINUSE' /tmp/vllm_glm5_master.log` — port collision
4. `grep 'KeyError.*indexer' /tmp/vllm_glm5_master.log` — indexer weight loading failure
5. `nvidia-smi --query-gpu=memory.used --format=csv,noheader` — if all < 2 GiB, OOM killed workers before loading
6. `ps aux | grep EngineCore | grep -v grep | wc -l` — if workers are gone but no Python error in log → silent death (OOM or crash before logging)