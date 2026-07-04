# Multi-Node vLLM (DP/EP) Initialization Debugging

For vLLM 0.6.0.dev0 (jasl/vllm ds4-sm120 branch) with multi-node Data Parallel.

## Symptom: EngineCore handshake timeout

Log shows:
```
RuntimeError: Did not receive response from front-end process within 5 minutes
```

**Root cause checklist** (in order of likelihood):

1. **SSH keys missing between nodes** — DP handshake uses SSH. Check bidirectionally:
   ```bash
   ssh jianliu@<other-node> "hostname"
   ```
   If it prompts for password, SSH keys are needed.

2. **`/etc/hosts` has 127.0.1.1 mapping** — Ubuntu default maps hostname to 127.0.1.1, causing Gloo to bind to loopback:
   ```
   RuntimeError: Gloo connectFullMesh failed: Connection refused, remote=[127.0.1.1]:17308
   ```
   Fix: remove the 127.0.1.1 entry and add the real IP.

3. **`--api-server-count 1` on headless worker** — headless nodes have no API server. Error:
   ```
   ValueError: --api-server-count=1 cannot be used with --headless
   ```
   Only set `--api-server-count` on master node. Worker gets `--headless` only.

4. **Port conflict** (stale processes) — previous kill may leave resource_tracker processes:
   ```bash
   ps aux | grep vllm | grep -v grep | awk '{print $2}' | xargs kill -9
   ```
   Then wait for ports to release before restarting.

## Successful Multi-Node Config (DeepSeek V4 Pro, 2 nodes)

### Master (oem96, 10.10.71.96):
TP=8, DP=2, EP=16, `--api-server-count 1`, `--gpu-memory-utilization 0.93`
IP network on `ens35f0np0` (RoCE v2, MTU 9000, ConnectX-6 Dx 100GbE)
NCCL: `NCCL_NET=IB`, `NCCL_IB_HCA=mlx5_0`, `NCCL_IB_DISABLE=0`

### Worker (oem98, 10.10.71.98):
Same args except `--headless --node-rank 1`, NO `--api-server-count`

### Launch order:
Worker first → then master (both via nohup + background SSH).

### Wait time:
Model loading + compilation (`compilation_config mode=3`) takes 3-8 minutes on first run. Log is very quiet during this phase — only ~28 lines on master until EngineCore initializes. Do NOT assume failure before 5+ minutes.

### Parameters Tested

**Note:** The `max-num-batched-tokens=32768` failures were not caused by SSH keys — they were caused by the 5-minute EngineCore handshake timeout. With SSH keys and /etc/hosts fixed, 32768 still failed. Only 16384 (with `--max-num-seqs 256` and `compile_ranges_endpoints=[8192,16384]`) successfully stayed under the timeout.

**UPDATED RESULT (2026-05-25, with SSH keys + fixed hosts + correct node-rank):**

| `max-num-batched-tokens` | `compile_ranges_endpoints` | `max-num-seqs` | Result |
|---|---|---|---|
| 8192 | None | 512 | ❌ timeout |
| 16384 | None | 512 | ❌ timeout |
| 8192 | None | 512 | ❌ timeout (tried again) |
| 16384 | `[8192,16384]` | 256 | ❌ KV cache OOM on worker |
| 16384 | `[8192,16384]` | 256 | ❌ KV cache still OOM (11.44 < 14.88) |
| 8192 | None | 512 | ❌ timeout (another attempt) |
| 8192 | None | 512 | ❌ timeout (with correct api-server default) |
| 16384 | `[8192,16384]` | 256 | ✅ SUCCESS (model-len 131072) |
| 16384 | `[8192,16384]` | 256 | ✅ SUCCESS (model-len 1048576) after also reducing max-num-seqs to 256 |

**Takeaway:** Three independent knobs controlled startup success:
1. `max-num-batched-tokens` 16384 (not 32768) — controls compilation + profiling work
2. `max-num-seqs` 256 (not 512) — controls CUDA graph capture scope
3. `compile_ranges_endpoints` matching `max-num-batched-tokens` — avoids un-compiled range

## Known Unsupported Flags

`--num-scheduler-steps`: Not supported in v0.6.0.dev0 (jasl/ds4-sm120 branch). Results in:
```
vllm: error: unrecognized arguments: --num-scheduler-steps 8
```
