# Multi-Node DP Diagnostics Reference

When investigating multi-node Data Parallel vLLM clusters, follow this checklist.

## Quick Triage (5 seconds)

```bash
# Check master node API
curl -s -o /dev/null -w '%{http_code}' http://<master-ip>:8000/health

# Expected: 200
# If FAIL: HTTP server may be down
```

## Prerequisite: SSH Key Auth Between Nodes

Before any DP cluster debugging, verify SSH key auth works in BOTH directions. The EngineCore handshake uses SSH; missing keys cause silent hang → 5-minute timeout.

```bash
# From master to worker
ssh jianliu@<worker-ip> "hostname"

# From worker to master
ssh jianliu@<master-ip> "hostname"
```

Both should return the hostname without prompting for password. If either fails, the DP cluster WILL NOT start — this is the #1 cause of multi-node DP failures.

## Full Diagnostic Flow

### 1. Master Node Health Check

```bash
ssh <user>@<master-ip> "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health"
```

`/health` returns 200 even if the engine is stuck. Always follow up.

### 2. Real Inference Test

```bash
ssh <user>@<master-ip> 'curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '\''{"model":"<model-name>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'\'''
```

Expect a response within 30 seconds. If it times out:
- Check GPU utilization (all GPUs should be near 100%)
- Check master logs for errors
- Check inter-node connectivity

### 3. Worker Node Check

Worker nodes have NO HTTP API. Verify they're alive via:

```bash
# Check EngineCore and Worker processes
ssh <user>@<worker-ip> "ps aux | grep -E 'VLLM::EngineCore|VLLM::Worker'"

# Check GPU utilization
ssh <user>@<worker-ip> "nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader"
```

Expected output (8 GPUs all near 100% util, ~93/96 GiB used for RTX PRO 6000):

```
0, 100 %, 92866 MiB
1, 100 %, 92866 MiB
...
```

### 4. Check Master Logs

```bash
ssh <user>@<master-ip> "tail -50 /tmp/vllm*.log | grep '200 OK'"
```

Look for `POST /v1/chat/completions HTTP/1.1 200 OK` entries.

### 5. Inter-Node Connectivity

```bash
# Ping between dedicated inter-node IPs
ssh <user>@<master-ip> "ping -c 2 <worker-interconnect-ip>"
ssh <user>@<worker-ip> "ping -c 2 <master-interconnect-ip>"
```

Expect < 1ms on dedicated 100G network.

### 6. System Resources

```bash
ssh <user>@<worker-ip> "free -h && df -h /"
```

## Common Patterns

| Symptom | Likely Cause |
|---------|-------------|
| curl to worker:8000 fails | ✅ Normal — only master serves HTTP |
| curl to master:8000 fails | HTTP server process crashed or not started |
| curl returns 200 but inference times out | EngineCore stuck — check GPU util and logs |
| GPUs at 0% util | Model loading / compilation still in progress |
| GPUs at 100% but no response | JIT compilation spike, or request stuck in queue |
| worker GPUs at 100%, master GPUs at 0% | Inter-node NCCL communication issue |
| Log shows engine started but 5 min later: "Did not receive response" | 🔴 SSH key auth missing between nodes — DP handshake failed |
| Log shows "EngineCore failed to start" with handshake timeout | 🔴 Check `ssh <user>@<remote-node> hostname` in both directions |

## Cluster Configuration Details (70.96 + 70.98)

| Field | Master (70.96) | Worker (70.98) |
|-------|----------------|----------------|
| Node rank | 0 | 1 |
| HTTP API port 8000 | ✅ Yes | ❌ No |
| Management IP | 10.10.70.96 | 10.10.70.98 |
| Interconnect IP | 10.10.71.96 | 10.10.71.98 |
| GPU count | 8× RTX 5090 (32 GB) | 8× RTX PRO 6000 (96 GB) |
| vLLM start | `bash start_dsv4_pro_2node.sh master` | `bash start_dsv4_pro_2node.sh worker` |
| API endpoint | http://10.10.70.96:8000 | N/A |
