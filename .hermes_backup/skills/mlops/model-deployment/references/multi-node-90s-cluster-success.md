# Multi-Node DeepSeek-V4-Pro Success Session (2026-05-25)

## Summary of the 70.96 (RTX 5090 8×) + 70.98 (RTX PRO 6000 8×) 2-node DP cluster

### Problem

Multi-node DP startup kept failing with `RuntimeError: Did not receive response from front-end process within 5 minutes`. Multiple attempts with varying parameters all timed out.

### Root Causes (3 independent issues, all needed fixing)

**1. SSH key auth missing between nodes** — EngineCore DP handshake uses SSH. Without passwordless auth in both directions, the handshake silently hangs until 5-minute timeout → `Gloo connectFullMesh failed: Connection refused`.

**2. `/etc/hosts` has 127.0.1.1** — Ubuntu default maps hostname `oem98` to `127.0.1.1`. Gloo binds to this loopback and cannot reach the remote node. Error: `Gloo connectFullMesh failed: SO_ERROR: Connection refused, remote=[127.0.1.1]:17308`.

**3. Worker `--node-rank` defaulting to 0** — Both nodes defaulted to `node-rank 0`. Error: `RuntimeError: HELLO message from remote engine 0, expected it to be local`.

### Additional Barriers (non-root but blocking)

**4. Leftover GPU processes** — After killing master vLLM, the worker node still had `VLLM::Worker` processes consuming all 91 GB VRAM on each GPU. Next startup failed: `Free memory on device cuda:N (4.98/94.97 GiB) is less than desired GPU memory utilization`.

**5. `--api-server-count 1` on headless** — Worker with `--headless` cannot have `--api-server-count`. Error: `ValueError: --api-server-count=1 cannot be used with --headless`. Resolution: omit `--api-server-count` entirely; defaults to `data_parallel_size` (2 on master, 0 on headless).

**6. KV cache sizing vs mixed GPU HBM** — DeepSeek-V4-Pro uses ~90 GB per node for weights. On 70.98's 96 GB RTX PRO 6000, only ~5-6 GB remains for KV cache. With `max-model-len=1048576`, vLLM needs ~24 GiB for KV cache → `ValueError: (24.06 GiB KV cache is needed, which is larger than available (1.01 GiB)`. Reducing `max-num-batched-tokens` from 32768 to 16384 freed enough memory for KV cache (raised available from 1.01 → 5.53 → 11.44 GiB). Combined with `max-num-seqs=256`, the startup succeeded.

**7. 5-minute EngineCore handshake timeout** — Even with all above fixed, initialization (model loading + KVCache profiling + torch.compile) took >5 minutes. Reducing `max-num-batched-tokens=16384` and `compile_ranges_endpoints=[8192,16384]` dropped init time below 300s.

### Working Configuration

```
# Master (70.96):
vllm serve /data/models/deepseekv4_pro \
  --distributed-executor-backend mp \
  --tensor-parallel-size 8 --pipeline-parallel-size 1 \
  --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend mp \
  --data-parallel-address 10.10.71.96 \
  --nnodes 2 --node-rank 0 \
  --master-addr 10.10.71.96 --master-port 29505 \
  --data-parallel-rpc-port 29550 \
  --enable-expert-parallel \
  --kv-cache-dtype fp8 --block-size 256 \
  --max-model-len 1048576 --gpu-memory-utilization 0.93 \
  --max-num-seqs 256 --max-num-batched-tokens 16384 \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"],"compile_ranges_endpoints":[8192,16384]}' \
  --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --served-model-name deepseek_v4_pro

# Worker (70.98): same, but:
#   --headless --node-rank 1
#   NO --api-server-count (must not appear)
```

### Throughput (Verified 2026-05-25)

| Metric | Value |
|--------|-------|
| 10×128/128 concurrent | 0.82 req/s, 105 out tok/s, TTFT=1585ms, TPOT=84ms |
| 20× ~10/256 Python | 1.1 req/s, 285 total tok/s, 17.1s e2e latency |
| Single short prompt TTFT | ~244ms |

### Startup Timeline (observed ~4 min)

```
t+0s    Worker starts
t+25s   Master starts
t+60s   Model loaded, compilation begins
t+120s  CUDA graph capture (PIECEWISE 51, FULL 35)
t+240s  Application startup complete
```
