# vLLM + GLM-5.1-FP8 Debugging Session — 2026-06-03

## Bugs Found Today

### 1. NameError: bare `indexer` instead of `"indexer"` string

**File**: `deepseek_v2.py` line ~1558 in `load_weights`
**Symptom**: All workers crash with `NameError: name 'indexer' is not defined`
**Visibility**: Completely hidden — master log only shows generic `WorkerProc initialization failed`
**Fix**:
```python
# WRONG
if not self.is_v32 and indexer in name:
# CORRECT
if not self.is_v32 and "indexer" in name:
```
**Diagnostic**: `grep -n 'and indexer in' deepseek_v2.py` to find all occurrences.

### 2. AttributeError: `'GlmMoeDsaForCausalLM' has no attribute 'is_v32'`

**Root cause**: `GlmMoeDsaForCausalLM` (line ~1726) inherits from `DeepseekV2ForCausalLM`.
`is_v32=False` was only set in `DeepseekV2Attention.__init__` (lines ~990, ~1221) — NOT in
`DeepseekV2ForCausalLM.__init__`. The model loader (inherited from parent class) checks
`self.is_v32` before the attention module is instantiated, causing AttributeError.
**Fix**: Set `self.is_v32 = False` in THREE places:
1. `DeepseekV2Attention.__init__` line ~990
2. `DeepseekV2Attention.__init__` line ~1221
3. `DeepseekV2ForCausalLM.__init__` line ~1384 (NEW — added today)
**Verification**:
```bash
grep -n 'is_v32 = False' /data/vllm-ds4-sm120/vllm/model_executor/models/deepseek_v2.py
# Must show 3 occurrences
```

### 3. Triton MLA kernel shared memory OOF: 100 KB > 99 KB limit

**File**: `vllm/v1/attention/ops/triton_decode_attention.py`
**Symptom**: Server starts OK but first inference request crashes:
```
triton.runtime.errors.OutOfResources: shared memory, Required: 102400, Hardware limit: 101376
```
**Root cause**: `num_stages=2` in Triton MLA decode kernel doubles shared memory footprint.
Blackwell SM 12.0 has 99 KB hardware limit; kernel needs 100 KB with `num_stages=2`.
`--enforce-eager` does NOT fix — Triton JIT compiles at runtime regardless of CUDA graph.
**Fix**: Change ALL `num_stages=2` → `num_stages=1`:
```python
python3 -c "
content=open('vllm/v1/attention/ops/triton_decode_attention.py').read()
count=content.count('num_stages=2')
print(f'Replacing {count} occurrences')
content=content.replace('num_stages=2','num_stages=1')
open('vllm/v1/attention/ops/triton_decode_attention.py','w').write(content)
"
```
Then verify: `python3 -m py_compile` + sync to worker node.

### 4. Old Worker processes holding GPU memory (invisible via ps)

**Symptom**: `ps aux | grep vllm` shows only 1 process (APIServer) but GPU shows 47 GB used.
**Root cause**: vLLM spawns `VLLM::Worker_PP*` subprocesses that are children of an
already-exited parent — they're orphaned and `ps aux` on the main process won't show them.
**Fix**:
```bash
# Find worker processes by name (not just grep for python)
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
# Kill by PID from this output
kill -9 <pid1> <pid2> ...
```
**Prevention**: Always kill by PID returned from nvidia-smi compute apps, not just ps.

## Session Log

| Time | Event |
|------|-------|
| 11:52 | Initial start attempt — NCCL connects OK but workers crash |
| 11:56 | Worker PP1 processes crash (EADDRINUSE on port 29505) |
| 12:02 | NameError found (bare `indexer` variable) — patched |
| 12:11 | AttributeError found (missing `is_v32` in DeepseekV2ForCausalLM) — patched |
| 12:17 | Server starts but first inference → XQA MLA head_group_ratio error |
| 12:18 | TRITON_MLA restored via startup script |
| 12:20 | Server starts, workers loading model |
| 12:27 | Server fully up, /v1/models returns glm5_1_fp8 |
| 12:28 | Inference request → Triton MLA shared memory OOF (100KB > 99KB) |
| 12:32 | num_stages=2 → num_stages=1 patched |
| 12:33 | Server restarted |
| 16:xx | Resume NVFP4 download |