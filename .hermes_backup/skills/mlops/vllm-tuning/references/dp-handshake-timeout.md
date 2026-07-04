# DP Handshake Timeout — Updated Root Cause Analysis

## Symptom

EngineCore fails with:
```
RuntimeError: Did not receive response from front-end process within 5 minutes
Engine core initialization failed. See root cause above. Failed core proc(s): {}
```

Both master and worker node logs show identical error. No Gloo, NCCL, or CUDA errors in the log above — just the timeout.

## Root Cause (Original)

In `/data/vllm-ds4-sm120/vllm/v1/engine/core.py`, line 1046:

```python
HANDSHAKE_TIMEOUT_MINS = 5
# ...
raise RuntimeError("Did not receive response from front-end process within 5 minutes")
```

Hardcoded 300-second timeout for `DPEngineCoreProc.startup_handshake`. Fires when model loading + KVCache profiling + CUDAGraph warmup on ALL worker processes exceeds 300s.

## NEW Finding: More Likely Failure Point

The 5-minute timeout is often a **red herring**. The real failure is usually one of these:

### 1. Worker Node Stalls Before Starting Engine Core

If the headless worker's front-end process encounters any error before launching its engine core, master waits forever. Example from this session:

**Worker error (not a timeout at all):**
```
ValueError: --api-server-count=1 cannot be used with --headless
(no API servers are started in headless mode).
```

The worker crashed immediately. Master's engine core sent HELLO to master's front-end, master's front-end sent init, engine core loaded model, but 70.98 never sent HELLO because it never launched. Result: master waited 5 minutes for the remote HELLO, then timed out. The error message says "timeout" but the root cause was `--api-server-count 1` on the headless node.

### 2. ZMQ Port Already in Use

Master fails to bind the ZMQ ROUTER socket for handshake:
```
ZMQError: Address already in use (addr='tcp://10.10.71.96:29550')
```

This happens when a previous vLLM process holds the port after being killed. The `fuser` approach doesn't clean ZMQ ports reliably because no TCP socket exists.

**Fix:** `fuser -k 29550/tcp` then verify `ss -tlnp | grep 29550` is empty. Also check for zombie `VLLM::*` named processes via `ps aux | grep VLLM`.

### 3. Genuine 5-Minute Timeout (Rare)

If nodes start cleanly and ports are free but the timeout still fires, it means model loading + compilation takes >5 min. This is possible with `mode=3` (VLLM_COMPILE) on a 806GB model.

## Step-by-Step DP Startup Diagnosis

When DP handshake fails, check in this order:

**Step 1 — Did worker (98) start cleanly?**
```bash
ssh 98 "tail /tmp/vllm_tp8_dp2.log | grep -i 'error\|traceback\|ValueError'"
```
Common blocker: `--api-server-count 1` on headless node (remove it).

**Step 2 — Is the handshake port listening on 96?**
```bash
ssh 96 "ss -tlnp | grep 29550"
```
If empty, the master never got to the bind call. Check master log for errors.

**Step 3 — Is port 29550 free before starting?**
```bash
ssh 96 "fuser -k 29550/tcp 2>/dev/null; sleep 1"
ssh 96 "fuser -v 29550/tcp 2>/dev/null"  # should be empty
```

**Step 4 — Any zombie VLLM:: processes on either node?**
```bash
ssh 96 "ps aux | grep VLLM"
ssh 98 "ps aux | grep VLLM"
```
The `VLLM::*` named processes (EngineCore_DP1, Worker_DP1_*, etc.) hold CUDA memory even after their parent is killed. Kill them individually.

## Workarounds Tested

| Workaround | Result |
|-----------|--------|
| Remove `custom_ops:["all"]` | ❌ Still failed (actual cause was other issue) |
| Use `mode=0` (no torch.compile) | ❌ Still failed |
| Remove `--api-server-count` on headless | ✅ Fixed the API-SERVER-COUNT crash |
| Sequential start (worker then master) | ✅ Required but not sufficient |
| Adding `--disable-async-scheduling` | ❌ Flag doesn't exist in ds4-sm120 |
| Cleaning ZMQ port with fuser | ✅ Required to avoid port conflict |

## Recommended Procedure

1. Kill all vLLM processes on both nodes
2. Kill zombie `VLLM::*` processes holding CUDA memory
3. Free port 29550 on 96: `fuser -k 29550/tcp`
4. Verify GPUs idle: `nvidia-smi` shows ~14 MiB per card
5. Start worker 98 first
6. Start master 96 second
7. Wait 2-3 minutes, check logs for progress
8. If master shows `Started DP Coordinator process`, this is promising
9. If master log stops advancing (no new lines for 2+ minutes), check worker log
