# NCCL Compatibility with Blackwell (sm120)

## The Problem

NCCL 2.28.9 (shipped with `nvidia-nccl-cu130` via PyTorch 2.11.0 wheels) does NOT support NVIDIA Blackwell architecture (compute capability 12.0). This causes `ncclCommInitRank` to fail with:

```
RuntimeError: NCCL error: invalid usage (run with NCCL_DEBUG=WARN for details)
```

The error trace is:
```
gpu_worker.py:281 → init_worker_distributed_environment
→ ensure_model_parallel_initialized → initialize_model_parallel
→ init_model_parallel_group → GroupCoordinator.__init__
→ device_communicator = cuda_communicator → PyNcclCommunicator.__init__
→ ncclCommInitRank → NCCL_ERROR: invalid usage
```

## System vs Venv NCCL

| Location | Version | Supports Blackwell? |
|----------|---------|-------------------|
| `/usr/lib/x86_64-linux-gnu/libnccl.so.2` | 2.30.4 (apt package) | ✅ Yes |
| `/data/venvs/vllm-ds4/.../nvidia/nccl/lib/libnccl.so.2` | 2.28.9 (pip wheel) | ❌ No |

## The Fix

Copy the system NCCL into the venv:

```bash
# On BOTH nodes:
SYS_NCCL=/usr/lib/x86_64-linux-gnu/libnccl.so.2.30.4
VENV_NCCL_DIR=/data/venvs/vllm-ds4/lib/python3.12/site-packages/nvidia/nccl/lib
VENV_TORCH_DIR=/data/venvs/vllm-ds4/lib/python3.12/site-packages/torch/lib

# Replace both copies
cp "$SYS_NCCL" "$VENV_NCCL_DIR/libnccl.so.2"
cp "$SYS_NCCL" "$VENV_TORCH_DIR/libnccl.so.2.30.4"
cd "$VENV_TORCH_DIR" && ln -sf libnccl.so.2.30.4 libnccl.so.2
```

## Verification

Start vLLM and check the startup logs for:
```
vLLM is using nccl==2.30.4
```

To check at runtime:
```bash
/data/venvs/vllm-ds4/bin/python3 -c "
from ctypes import CDLL
l = CDLL('libnccl.so.2')
v = l.ncclGetVersion()
print(f'NCCL version: {v}')
# Version encoding: 23004 = 2.30.4, 22809 = 2.28.9
"
```

## Important: The `NCCL_IB_DISABLE=1` TCP Fallback Path

Before discovering the NCCL version issue, we tried `NCCL_IB_DISABLE=1` + `NCCL_NET=Socket` to bypass IB verbs. **This does NOT fix the NCCL 2.28.9/sm120 incompatibility** — the `ncclCommInitRank` error is a CUDA-level peer init issue, not an IB transport issue. TCP fallback works around the `unhandled system error` (NCCL IB state corruption), not the `invalid usage` (sm120 incompatibility).

## Persistence

The NCCL 2.30.4 replacement survives venv re-activation but will be overwritten if the venv is recreated or torch is upgraded via pip. After any `pip install` that touches torch, re-apply the copy commands.
