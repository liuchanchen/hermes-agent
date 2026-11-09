# Multi-Node vLLM DP Restart Reference (70.96 + 70.98)

Current production config for the DeepSeek-V4-Pro 2-node DP cluster.

## Current Working Configuration (as of 2026-05-25)

| Parameter | Value |
|-----------|-------|
| TP | 8 |
| DP | 2 (70.96 master + 70.98 worker) |
| EP | 16 (flattened across both nodes) |
| Model | `/data/models/deepseekv4_pro` |
| Port | 8000 (master only) |
| max-model-len | 1048576 |
| max-num-batched-tokens | **16384** |
| max-num-seqs | **256** |
| gpu-memory-utilization | 0.93 |
| kv-cache-dtype | fp8 |
| compilation-config | `{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"],"compile_ranges_endpoints":[8192,16384]}` |
| RoCE/NIC | ens35f0np0 (100GbE) |
| Inter-node IPs | 10.10.71.96 / 10.10.71.98 |
| vLLM version | v0.6.0.dev0 (jasl/vllm ds4-sm120 branch) |
| --api-server-count | **OMIT** (defaults to data_parallel_size) |

## PRIOR to First-Time Startup on New/Bare-Metal Nodes

These steps only need to be done once per cluster setup, but RE-CHECK them before every session — they have caused silent failures after OS updates, SSH key rotation, or user provisioning:

### 1. SSH Key Auth (BIDIRECTIONAL)

Multi-node vLLM DP handshake uses SSH. Without passwordless auth, startup silently hangs for 5 minutes then times out.

**Check:**
```bash
ssh jianliu@10.10.70.98 "hostname"   # from 70.96
ssh jianliu@10.10.70.96 "hostname"   # from 70.98
```
Both must return hostname without password prompt.

**Fix if missing:**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub | ssh jianliu@<OTHER-IP> "cat >> ~/.ssh/authorized_keys"
```

### 2. /etc/hosts Fix (Ubuntu Default Bug)

Ubuntu writes hostname to `127.0.1.1`, causing Gloo to bind to loopback.

**Check:**
```bash
hostname -i
```
Must return `10.10.71.X`, NOT `127.0.1.1`.

**Fix:**
```bash
# Manual (requires approval):
sudo sed -i '/HOSTNAME/d' /etc/hosts
echo "10.10.71.X  HOSTNAME" | sudo tee -a /etc/hosts
```

### 3. Verify GPU Memory is Clean

Leftover `VLLM::Worker` processes can consume 100% VRAM after a crash or forced kill.

**Check:**
```bash
nvidia-smi | grep VLLM
```

**Fix:** Kill all leftover VLLM processes by PID:
```bash
ps aux | grep -E 'vllm|VLLM' | grep -v grep | awk '{print $2}' | xargs kill -9
```

## Restart Procedure

```bash
# 1. Kill on BOTH nodes
ssh jianliu@10.10.70.96 "ps aux | grep python | grep vllm | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null; sleep 2"
ssh jianliu@10.10.70.98 "ps aux | grep python | grep vllm | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null; sleep 2"

# 2. Clean GPU memory on worker (critical step!)
ssh jianliu@10.10.70.98 "nvidia-smi | grep VLLM"
ssh jianliu@10.10.70.98 "kill -9 <LEFT OVER PIDS>"

# 3. Start WORKER first, then MASTER
ssh jianliu@10.10.70.98 "source ~/.bashrc && bash /tmp/launch_vllm.sh"
ssh jianliu@10.10.70.96 "source ~/.bashrc && bash /tmp/launch_vllm.sh"
```

## Launch Scripts

- Master (70.96): `/tmp/launch_vllm.sh` — has `--node-rank 0`, NO `--headless`
- Worker (70.98): `/tmp/launch_vllm.sh` — has `--headless --node-rank 1`, NO `--api-server-count`

Both scripts use `--gpu-memory-utilization 0.93`, `--max-num-batched-tokens 16384`, `--max-num-seqs 256`.

## Startup Timeline (observed ~4 min)

```
t+0s    Worker starts, initializes model on all 8 GPUs
t+25s   Master starts, initializes model
t+60s   Model loaded (~56 GB/GPU), compilation begins
t+120s  Torch Inductor compilation (mode=3) — CUDA graph capture
t+240s  Application startup complete — server ready
```

## Verifying Server is Ready

Only the master node has an HTTP API:
```bash
curl -s http://10.10.71.96:8000/health
curl -s http://10.10.71.96:8000/v1/models
curl -s -X POST http://10.10.71.96:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek_v4_pro","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

The worker node (10.10.71.98) has NO port 8000 — that's by design. Check worker via:
```bash
ssh jianliu@10.10.70.98 "ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker' | head -3"
```

## Known Failure Modes

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `Gloo bind to [127.0.1.1]` | /etc/hosts | Fix 127.0.1.1 → real IP |
| Connection refused / timeout | SSH keys missing | Configure bidirectional SSH |
| `HELLO message from remote engine 0` | Worker needs --node-rank 1 | Add `--node-rank 1` to worker |
| `--api-server-count=1 cannot be used with --headless` | api-server-count on headless | Omit from worker script |
| `KV cache 24 GiB needed, only 1/5/11 GiB available` | max-num-batched-tokens too high | Reduce to 16384, seqs to 256 |
| `5-minute timeout` | EngineCore init too slow | Reduce batched-tokens + compile_ranges |
| `VLLM::Worker` on GPU after kill | Leftover processes | Check nvidia-smi after every kill |
| `HELLO timeout` on first start even with correct config | Model loading + compile | Wait 4-6 minutes, log is quiet |
