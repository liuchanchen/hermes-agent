# Multi-node DP Debugging: 70.96 (oem96) + 70.98 (oem98)

## Cluster Configuration

| Node | IP | GPU | HBM | Role |
|------|-----|-----|-----|------|
| oem96 | 10.10.71.96 | RTX 5090 ×8 | 32 GB each | Master (node-rank 0) |
| oem98 | 10.10.71.98 | RTX PRO 6000 BW SE ×8 | 96 GB each | Worker (node-rank 1) |

## Final Working Parameters

```bash
vllm serve /data/models/deepseekv4_pro \
  --host 0.0.0.0 --port 8000 \
  --distributed-executor-backend mp \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 1 \
  --data-parallel-size 2 --data-parallel-size-local 1 \
  --data-parallel-backend mp \
  --data-parallel-address 10.10.71.96 \
  --nnodes 2 --node-rank 0 \           # master uses rank 0
  --master-addr 10.10.71.96 --master-port 29505 \
  --data-parallel-rpc-port 29550 \
  --enable-expert-parallel \
  --kv-cache-dtype fp8 --block-size 256 \
  --max-model-len 1048576 \
  --gpu-memory-utilization 0.93 \
  --max-num-seqs 256 --max-num-batched-tokens 16384 \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"],"compile_ranges_endpoints":[8192,16384]}' \
  --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --served-model-name deepseek_v4_pro
```

Worker adds `--headless` and `--node-rank 1`. No `--api-server-count`.

## Debugging Timeline (from "keeps failing" to "working")

Each step below identifies an error that was fixed by the subsequent change:

### 1. SSH key auth missing between nodes
**Error**: `RuntimeError: Did not receive response from front-end process within 5 minutes` on master node EngineCore, no Gloo/NCCL errors visible.

**Fix**: 70.96's public key was added to 70.98's `~/.ssh/authorized_keys`. Verified with `ssh jianliu@10.10.70.98 "hostname"` from 70.96.

### 2. Hostname resolves to 127.0.1.1 on worker
**Error**: `Gloo connectFullMesh failed: Connection refused, remote=[127.0.1.1]:17308` — 70.98's hostname resolution returned loopback.

**Fix**: Edited `/etc/hosts` on 70.98:
```bash
sudo sed -i '/oem98/d' /etc/hosts
echo '10.10.71.98  oem98' | sudo tee -a /etc/hosts
```
Confirmed with `hostname -i` returning `10.10.71.98`.

### 3. Worker misidentifies as rank 0 (missing --node-rank)
**Error**: `HELLO message from remote engine 0, expected it to be local`

**Fix**: Explicitly set `--node-rank 0` on master and `--node-rank 1` on worker. Both default to 0 when omitted, causing the engine to reject cross-node handshake.

### 4. Worker GPU memory insufficient for KV cache
**Error**: `ValueError: To serve at least one request with the models's max seq len (1048576), (14.88 GiB KV cache is needed, which is larger than the available KV cache memory (11.44 GiB)... estimated maximum model length is 411904.` on 70.98's EngineCore.

The 96 GB RTX PRO 6000 loads ~90 GB of model weights, leaving only 5-6 GB for KV cache. With `max-model-len=1048576` and `block-size=256`, vLLM needs ~24 GB KV cache even with TP=8 and FP8.

**Fix**: Reduced `max-num-batched-tokens` from 32768 to 16384, which reduced compile/KV profiling memory overhead enough to fit (11.44 GB → just enough after also reducing `max-num-seqs` from 512 to 256). Key insight: `max-num-batched-tokens` is the primary lever for startup success, not `max-num-seqs` (which doesn't affect KV cache allocation).

### 5. 5-minute EngineCore handshake timeout from excessive compile work
**Error**: Repeated `RuntimeError: Did not receive response from front-end process within 5 minutes` on EngingCore startup even with SSH and hosts fixed.

**Fix**: `max-num-batched-tokens=32768` with `compile_ranges_endpoints=[8192,16384,32768]` caused Torch Inductor compilation to exceed 300s. Dropping to `max-num-batched-tokens=16384` with `compile_ranges_endpoints=[8192,16384]` brought init time under 5 min.

## Key Lessons

1. **`max-num-batched-tokens` is the primary startup-time lever for vLLM 0.6.0.dev0 ds4-sm120** — not `max-model-len`. Reducing from 32768 to 16384 fixed both the 5-minute timeout AND freed enough memory for KV cache.
2. **Mixed GPU clusters require matching the smallest HBM capacity** — 32 GB ×8 (5090) + 96 GB ×8 (PRO 6000) is tricky because the 96 GB node loads more weights per-GPU due to different TP memory layout.
3. **SSH keys expire / can be overwritten** — always re-verify before debugging anything else.
4. **Ubuntu defaults to `127.0.1.1` for hostname** — always check `/etc/hosts` when Gloo connections fail with loopback addresses.
5. **`--api-server-count` should be OMITTED** — letting it default to `data_parallel_size` works correctly (2 on master, 0 on headless). Explicit `--api-server-count 1` on master is fine but unnecessary; on headless it's a hard error.
