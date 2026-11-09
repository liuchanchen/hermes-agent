# DeepSeek-V4-Flash-0731 Download to 192.168.12.12

**Date**: 2026-08-02 (initial), 2026-08-03 (continued)
**Target**: 192.168.12.12 → `/home/public/models/deepseekv4-flash-0731/`
**ModelScope ID**: `deepseek-ai/DeepSeek-V4-Flash-0731`
**ModelScope page**: https://www.modelscope.cn/models/deepseek-ai/DeepSeek-V4-Flash-0731
**Container**: `jianliu_sw2_public_19255` (image `10.10.91.56/sw2/sw2_public`)
**Endpoint**: `https://www.modelscope.cn` (via `MODELSCOPE_ENDPOINT` env var)

## Download Command

```bash
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && /opt/conda/envs/sw2_public/bin/modelscope download --model deepseek-ai/DeepSeek-V4-Flash-0731 --local_dir /home/public/models/deepseekv4-flash-0731/ --max-workers 8 2>&1'"
```

## Model Details

- **Total size**: ~159 GB (48 safetensor shards, ~3.3 GB each)
- **Shards**: `model-00001-of-00048.safetensors` through `model-00048-of-00048.safetensors`
- **Config file**: `config.json` (DeepSeek-V4-Flash HuggingFace format)
- **No `--force` flag** — CLI does not support it; omit

## Container Environment

- Conda env: `/opt/conda/envs/sw2_public/` (Python 3.12)
- modelscope path: `/opt/conda/envs/sw2_public/bin/modelscope`
- modelscope package: pre-installed in that env (no pip install needed)
- Python: `/opt/conda/envs/sw2_public/bin/python3.12`
- **~/.bash_alias does NOT exist on 12.12** — always use `docker exec` directly

## Progress Tracking

```bash
# Disk usage + shard count (primary progress signal)
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/; ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# Running process count
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep modelscope | grep -v grep'"

# Clean kill all running downloads before restart
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'pkill -f modelscope download'"

# One-liner kill + verify
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep \"modelscope download\" | grep -v grep | grep python | awk \"{print \\\$2}\" | xargs kill 2>/dev/null; sleep 2; ps aux | grep modelscope | grep -v grep | wc -l'"
```

## SSH Output Buffering (Critical — Session 2026-08-03)

Download stdout can be **silently buffered for 10–20 minutes** through the SSH tunnel, even with `PYTHONUNBUFFERED=1` in the environment. The SSH channel process shows `status: running` with growing `uptime_seconds`, but download progress lines do NOT appear in the output log.

**Symptom pattern:**
- `process poll` shows same output (conda error + "1" process count)
- `uptime_seconds` grows by hundreds every check (process is alive)
- `du -sh` shows no growth for 10+ minutes despite process running
- Download still running inside container after SSH reconnects

**Rule:** Never wait for download stdout to update. Always use independent disk-check background commands as the primary progress signal. If disk size is unchanged after 5+ minutes with running process, the modelscope process may be stuck in a TLS/network handshake → kill and restart.

## Server Overload Escalation Pattern

When 12.12 is under heavy load, all SSH connections fail simultaneously with:
- `kex_exchange_identification: read: Connection reset by peer`
- `Connection closed by 192.168.12.12 port 22`

Immediate retries all fail. Server recovers after 5-15 minutes.

**Correct response:** Submit 3 background checks with escalating delays simultaneously:

```bash
sleep 60  && ssh -o ConnectTimeout=120 ... du -sh ...   # fires in 60s
sleep 300 && ssh -o ConnectTimeout=120 ... du -sh ...   # fires in 5min
sleep 600 && ssh -o ConnectTimeout=120 ... du -sh ...   # fires in 10min
```

**NEVER:** tight `sleep 5 && ssh...` loop.

## Known Issues

1. **Host conda broken**: `~/.bash_alias` absent on 12.12; host miniconda3 activation throws `TypeError` on every SSH. Fix: always use `ssh -T` to bypass PTY/host init.
2. **SSH connection drops**: 12.12's SSH daemon floods under heavy concurrent connections + model download load. Each drop spawns a new background download process. Fix: always check/kill old processes before re-running.
3. **Multiple-process pile-up**: Without cleanup, 2-3+ duplicate download processes compete for bandwidth. New SSH retry spawns a new process even if old one is still running.
4. **Output buffering**: `tqdm` progress output is line-buffered over SSH pipe; may appear stale in terminal output. Use disk checks, not stdout, for progress.

## Download Speed Notes

Speeds vary dramatically per shard and connection quality:
- Fast shard completion: 1.8 GB/s (burst, cached or local)
- Typical download: 200–600 kB/s per shard
- Slow shards: 50–100 kB/s (network congestion)
- Multiple parallel shards (max 8 workers) can saturate available bandwidth

## Download State History

| Date | Size | Shards | Notes |
|------|------|--------|-------|
| 2026-08-02 early | 88GB | 46/48 | SSH dropped, resumed |
| 2026-08-02 mid | 100GB | 46/48 | 2 processes competing, killed |
| 2026-08-02 mid | 103GB | 46/48 | Cleaned up |
| 2026-08-02 late | 108GB | 46/48 | model-00006 @92%, model-00009 @90% |
| 2026-08-03 early | 99GB | 46/48 | SSH reset, retry |
| 2026-08-03 | 100GB | 46/48 | PIDs 4038122+4112689+4112694 killed |
| 2026-08-03 | 103GB | 46/48 | PID 4137322 continues |
| 2026-08-03 | 105GB | 46/48 | 2 processes (killed old) |
| 2026-08-03 | 106GB | 46/48 | PIDs 4137322+4172409 running |
| 2026-08-03 | 107GB | 46/48 | PIDs 4137322 killed, PID 813 continues |
| 2026-08-03 | 108GB | 46/48 | PID 4172409 continues |
| 2026-08-03 | 109GB | 46/48 | PID 813 + 33704 running, 813 killed |
| 2026-08-03 | 110GB | 46/48 | PID 33704 continues |
| 2026-08-03 end | 111GB | 46/48 | ~47GB remaining (2 shards × 3.3GB) |
| 2026-08-03 late | 112GB | 46/48 | PID 33704 only, staggered checks running |
| 2026-08-03 | 114GB | 46/48 | proc_95bf4eddafcc running 38min, no output (buffered) |
| 2026-08-03 | 115GB | 46/48 | Same proc ~43min, disk growing |
| 2026-08-03 | 116GB | 46/48 | SSH overload, staggered checks active. ~43GB remaining |

## Download completion criteria

1. `ls *.safetensors | wc -l` == 48
2. `du -sh` total size == ~158GB
3. `ps aux | grep modelscope | wc -l` == 0 (no process running)