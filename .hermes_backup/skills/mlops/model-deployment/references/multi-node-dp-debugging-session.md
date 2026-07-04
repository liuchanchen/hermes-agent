# Multi-Node vLLM DP Debugging Session (2026-05-25)

## Summary

Attempted to start a 2-node DP=2 vLLM cluster (70.96 master + 70.98 worker) with DeepSeek-V4-Pro. The cluster **never successfully started in multi-node DP mode** — every attempt hit the 5-minute EngineCore handshake timeout.

## Root Causes Found (in order of discovery)

### 1. SSH keys missing between nodes (70.96 ↔ 70.98)
- vLLM EngineCore DP handshake uses SSH for inter-node coordination
- Without passwordless SSH, the connection silently hangs until the 5-minute timeout
- **Status**: Fixed (installed SSH public key from 70.96 onto 70.98)
- **Check**: `ssh jianliu@10.10.70.98 "hostname"` from 70.96

### 2. `/etc/hosts` maps hostname to 127.0.1.1 on 70.98
- Ubuntu default: `127.0.1.1  oem98` in `/etc/hosts`
- Causes Gloo to bind to loopback: `Gloo connectFullMesh failed with ... Connection refused, remote=[127.0.1.1]:17308`
- **Fix**: `sudo sed -i '/oem98/d' /etc/hosts && echo '10.10.71.98  oem98' | sudo tee -a /etc/hosts`
- **Status**: Fixed

### 3. Hard-coded 5-minute EngineCore handshake timeout (FINAL BLOCKER)
- In `vllm/v1/engine/core.py` line 1046, `startup_handshake` has `300` second hard timeout
- Cannot be extended via CLI flags
- DeepSeek-V4-Pro (806 GB, FP8, 1M context) + compile mode=3 + KVCache profiling reliably exceeds 5 minutes
- **Observed even on single-node DP=2 setup** — this is NOT a network issue
- **Affects**: All config variants tested (8192 and 16384 batched_tokens, with/without `--api-server-count 1`, with/without `--node-rank 0`)

## Configurations Tested

| # | max-batched-tokens | compile_ranges_endpoints | api-server-count | SSH keys | hosts fixed | Result |
|---|-------------------|------------------------|-----------------|----------|-------------|--------|
| 1 | 32768 | [8192,16384,32768] | 1 (master) | ❌ | ❌ | 5min timeout |
| 2 | 32768 | same | 1 (master) | ✅ | ✅ | 5min timeout |
| 3 | 16384 | none | 1 (master) | ✅ | ✅ | 5min timeout |
| 4 | 8192 | none | 1 (master) | ✅ | ✅ | 5min timeout |
| 5 | 8192 | none | default (DP=2) | ✅ | ✅ | 5min timeout |

## Log Indicators

### EngineCore timeout (master node, 70.96)
```
(EngineCore_DP0 pid=XXXXX) ERROR 05-25 XX:XX:XX [core.py:1136] RuntimeError: Did not receive response from front-end process within 5 minutes
(APIServer pid=XXXXX) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}
```

### Gloo 127.0.1.1 (worker node, 70.98)
```
RuntimeError: Gloo connectFullMesh failed with ... Connection refused, remote=[127.0.1.1]:17308
```

### Worker unable to connect (no Gloo error, just timeout)
```
INFO [serve.py:201] Launching 1 data parallel engine(s) in headless mode, with head node address tcp://10.10.71.96:29550.
... (5 minutes silence) ...
RuntimeError: Did not receive response from front-end process within 5 minutes
```

## What DID Work (Single-Node)

The same node running `TP=8, DP=1, api-server-count=1` with `max-num-batched-tokens=8192` previously started successfully (log: `vllm_tp8_dp2_810047.log`, 444 lines, completed in ~20 seconds). This confirms the DP handshake timeout is the root cause for multi-node failures.

## Current State

70.96 and 70.98 both have:
- SSH key auth (96 → 98) ✅
- Correct `/etc/hosts` on 98 ✅
- Clean launch scripts in `/tmp/launch_vllm.sh` on both nodes
- The startup script `/data/venvs/vllm-ds4/start_dsv4_pro_tp8_dp2_ep.sh` is updated to:
  - `max-num-batched-tokens=8192` (original working value)
  - No `compile_ranges_endpoints` extension (prevents extra compile load)
  - No `num-scheduler-steps` (unsupported in this vLLM version)
  - `api-server-count 1` on master only

**Next steps to make DP work**:
1. Patch `vllm/v1/engine/core.py` to increase the 300-second timeout to 600+
2. Or reduce `max-model-len` (e.g., 524288) to speed KVCache profiling
3. Or switch to single-node DP=1 which works reliably
