# EngineCore Silent Death — Worker Node Version Mismatch

**Date**: 2026-06-03
**Nodes**: 10.10.70.96 (master) + 10.10.70.98 (worker)
**Model**: GLM-5.1-FP8, PP=2, TP=8, 2-node Blackwell cluster

## Symptom

Both nodes start the startup script. Worker (PP1) appears to initialize and connect to NCCL.
Master (PP0) starts. Then the cluster hangs indefinitely. The master log shows:

```
Failed core proc(s): {}
```

No ERROR, no Traceback, no exception from the worker processes. The worker logs show no
indication that anything went wrong — they simply appear to exit.

## Root Cause

**Worker (70.98) was running pre-built pip-installed vLLM** (v0.1.dev1) instead of the
ds4-sm120 editable install (v0.6.0.dev0+cu132).

Despite both nodes having `/data/vllm-ds4-sm120/` with the custom vLLM branch, the
worker's Python path was resolving to the wrong package. The editable install metadata
pointed to different site-packages on each node.

Workers died during model loading because the vLLM version doing the loading was a
different codebase than the master's. Model weight loading in v0.1.dev1 vs v0.6.0.dev0
has incompatibilities.

The error was **silent**: Workers crashed without writing any error to stdout/stderr,
so the parent `MultiNodeInferencePool` only received the generic "failed core proc(s)"
message with no details.

## Key Diagnostic Commands

```bash
# Check vLLM version and install location on both nodes
ssh 70.96 "source /data/venvs/vllm-ds4/bin/activate && vllm --version && python3 -c 'import vllm; print(vllm.__file__)'"
ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && vllm --version && python3 -c 'import vllm; print(vllm.__file__)'"

# Check pip install metadata
ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && pip show vllm | grep -E 'Version|Location|Editable'"

# Check if vllm process is running on worker
ssh 70.98 "ps aux | grep '[v]llm'"

# Check if GPU is in use on worker (worker should hold ~42 GiB/GPU when loading)
ssh 70.98 "nvidia-smi --query-gpu=index,memory.used --format=csv,noheader"
```

## The Fix

```bash
# On worker, reinstall the ds4-sm120 branch as editable
ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && \
  pip install -e /data/vllm-ds4-sm120/ --no-deps --force-reinstall"

# Verify
ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && vllm --version && python3 -c 'import vllm; print(vllm.__file__)'"
# Must show: 0.6.0.dev0+cu132 and /data/vllm-ds4-sm120/vllm/__init__.py
```

## Prevention

Run the version verification **before every restart**:
```bash
for node in 70.96 70.98; do
  echo "=== $node ==="
  ssh $node "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
done
```

Both must show `0.6.0.dev0+cu132` and the `__file__` must point to `/data/vllm-ds4-sm120/`.