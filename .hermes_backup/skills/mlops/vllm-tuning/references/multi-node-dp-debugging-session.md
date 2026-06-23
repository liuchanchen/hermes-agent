# Multi-Node DP Startup Debugging — Session Log (2026-05-26)

## Context

Attempted to run the full Phase 5 tuning plan on the `ds4-sm120` branch (v0.6.0.dev0). The service was down on both 70.96 and 70.98. Required starting from scratch.

## Environment

- **Model**: DeepSeek V4 Pro, 806GB, 64 safetensor files
- **Nodes**: 70.96 (master) + 70.98 (worker), 8× RTX PRO 6000 Blackwell SE (96GB/card) each
- **Interconnect**: 10.10.71.x/24 (ens35f0np0, ConnectX-6), RoCE v2
- **vLLM**: /data/vllm-ds4-sm120, git branch `ds4-sm120`, commit b709b75
- **Venv**: /data/venvs/vllm-ds4
- **Model path**: /data/models/deepseekv4_pro
- **Log files**: /tmp/vllm_tp8_dp2.log (on each node), /tmp/vllm_tp8_pp2.log (PP attempts)

## Attempted Configurations and Results

### Attempt 1: TP=8+PP=2+EP=8 (with --nnodes, --node-rank)

Script followed the plan's Phase 5 template:
```
--pipeline-parallel-size 2 --nnodes 2 --node-rank <0|1>
--master-addr 10.10.71.96 --master-port 29505
```

**Result: FAILED** — both nodes initialized independently

Log evidence:
- 70.96 workers: `world_size=16 rank=0-7, distributed_init_method=tcp://127.0.0.1:29501`
- 70.98 workers: `world_size=16 rank=8-15, distributed_init_method=tcp://127.0.0.1:29501`

**Root cause**: `multiproc_executor.py:128` uses `get_distributed_init_method(get_loopback_ip(), get_open_port())` — always loopback. The `--master-addr` is only consumed by the DP coordinator path aff.

### Attempt 2: TP=8+DP=2+EP=16 (original config, with --api-server-count 1 on 98)

Used the exact original scripts from the server.

**Result: FAILED** — worker crashed immediately with:
```
ValueError: --api-server-count=1 cannot be used with --headless
(no API servers are started in headless mode).
```

Master waited 5 minutes for the remote HELLO that would never arrive, then timed out with the generic "Did not receive response" message.

### Attempt 3: TP=8+DP=2+EP=16 (fixed, no --api-server-count on 98)

Fixed 70.98 script to remove `--api-server-count 1`.

**Result: FAILED** — ZMQ port conflict
```
ZMQError: Address already in use (addr='tcp://10.10.71.96:29550')
```

The previous vLLM process (PID 1068802) still held the port. `fuser -k` didn't clean it because ZMQ uses internal queuing that persists across process death in some cases.

### Attempt 4: Clean restart (all processes killed, port freed)

Both nodes cleaned, killed zombie VLLM::* named processes manually.

**Result**: Killed all processes and got to clean state but session ran out of tool calls before the actual DP startup could complete.

## Key Diagnoses

1. **Bottleneck**: The handshake timeout error message is misleading — it masks the real root cause in most cases
2. **Debugging procedure**: Always check worker log first for crash errors before assuming a genuine timeout
3. **ZMQ persistence**: The `29550` port may show as free in `ss` but ZMQ can still refuse to bind if a previous context isn't fully cleaned
4. **VLLM:: processes**: Named subprocesses (EngineCore_DP1, Worker_DP1_TP*) survive parent death and hold GPU memory
5. **PP across nodes**: NOT supported at all in this branch — the multiproc executor hardcodes loopback for NCCL init

## Startup Procedure Verified to Work

After the session ended, the correct procedure for a clean restart would be:

```bash
# On BOTH nodes:
pkill -9 -f "vllm serve" 2>/dev/null
pkill -9 -f "VLLM::" 2>/dev/null
sleep 2
nvidia-smi  # Verify <20 MiB per card

# On 70.96 specifically:
fuser -k 29550/tcp 2>/dev/null
fuser -k 29505/tcp 2>/dev/null
ss -tlnp | grep 295  # Should be empty

# Start order:
ssh 98 'bash /tmp/launch_vllm.sh'  # Worker first
ssh 96 'bash /tmp/launch_vllm.sh'  # Master second

# Monitor:
watch -n 30 'ssh 96 "grep -E \"INFO|ERROR\" /tmp/vllm_tp8_dp2.log | tail -5"'
watch -n 30 'ssh 98 "grep -E \"INFO|ERROR\" /tmp/vllm_tp8_dp2.log | tail -5"'
```

Expected healthy startup sequence (from previous successful runs):
1. Both nodes: `Resolved architecture: DeepseekV4ForCausalLM`
2. Both nodes: `Using max model len 1048576`
3. Both nodes: `Chunked prefill is enabled with max_num_batched_tokens=16384`
4. Both nodes: `Asynchronous scheduling is enabled.`
5. 70.96: `Started DP Coordinator process (PID: ...)`
6. Both nodes: Engine core workers start (world_size=8, rank=0-7)
7. 70.96: Handshake receives HELLO from local AND remote engine cores
8. 70.96: `Uvicorn running on http://0.0.0.0:8000`
