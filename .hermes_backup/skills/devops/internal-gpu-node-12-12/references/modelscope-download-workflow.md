# ModelScope Download Workflow on 192.168.12.12

## Overview

Downloading models from ModelScope onto 192.168.12.12 uses the `jianliu_sw2_public_19255` Docker container which has the `sw2_public` conda environment pre-configured with modelscope.

## Verified Commands

### Download (always use full path, no `--force`)

```bash
ssh -T jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && \
     /opt/conda/envs/sw2_public/bin/modelscope download \
       --model deepseek-ai/DeepSeek-V4-Flash-0731 \
       --local_dir /home/public/models/deepseekv4-flash-0731/ \
       --max-workers 8'"
```

Key details:
- **Full path required**: `/opt/conda/envs/sw2_public/bin/modelscope` — not in default PATH
- **`--force` does NOT exist**: results in `unrecognized arguments: --force`
- **`--max-workers 8`**: good balance for parallel download
- **`ssh -T` is critical**: bypasses the broken conda init on the host's `.bashrc` (otherwise every line of output is preceded by a conda TypeError exception dump)
- Auto-resume works without `--force` — re-running the same command picks up from where it left off

### Progress Monitoring

```bash
# Shard count
ssh -T jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# Total size
ssh -T jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'du -sh /home/public/models/deepseekv4-flash-0731/'"

# Running processes (verify download is alive)
ssh -T jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'ps aux | grep modelscope | grep -v grep'"
```

## SSH Resilience Issues

The server SSH daemon (sshd) becomes temporarily unresponsive during large parallel downloads to the container — multiple concurrent SSH connections trigger `kex_exchange_identification: read: Connection reset by peer`. Pattern observed:
1. Start download → SSH works fine at first
2. After several minutes → sshd starts rejecting new connections with reset
3. After 5–10 minutes of no SSH attempts → sshd recovers

**Workaround**: Do NOT poll frequently. Wait 2–5 minutes between SSH attempts. If blocked, schedule a background check with `sleep 300 && ssh ...`.

## Process Management

When SSH drops mid-download, the actual download process inside the container **continues running**. On reconnect:
1. Check `ps aux | grep modelscope` to see if a process is still alive
2. If yes → wait for it to finish (do not start a second instance)
3. If no → re-run the download command (modelscope auto-resumes from existing files)
4. If multiple processes exist → kill all but the newest (oldest PIDs first), then re-run

To kill conflicting processes:
```bash
ssh -T jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'ps aux | grep \"modelscope download\" | grep -v grep | awk \"{print \\$2}\" | xargs kill 2>/dev/null'"
```

## Known ModelSpecs

| Model | Repo ID | Files | Total Size | Shard Size |
|-------|---------|-------|-----------|------------|
| DeepSeek-V4-Flash-0731 | `deepseek-ai/DeepSeek-V4-Flash-0731` | 48 .safetensors | ~158GB | ~3.3GB/shard |

## Container Environment

- **Container**: `jianliu_sw2_public_19255` (port 19255 exposed)
- **Conda env**: `sw2_public` (Python 3.12, at `/opt/conda/envs/sw2_public/`)
- **No pip in base image**: apt-get needed for system packages, but modelscope already installed
- **Disk**: 7.0TB overlay, ~2.2TB free (sufficient for any model on ModelScope)
- **`dkexec` alias**: Does NOT exist on this host — use `docker exec` directly