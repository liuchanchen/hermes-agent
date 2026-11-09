# ModelScope Download — 2026-08-05 Morning Session

## Session goal
Complete DeepSeek-V4-Flash-0731 download (48 safetensors, ~158GB) on 192.168.12.12.

## Key discoveries

### 1. Deleting small shard files triggers immediate parallel re-download

**Symptom:** `du -sh` growing (~1GB/5min) but `ls | wc -l` stuck at 47/48 for 20+ minutes with 1 process running. The process is NOT stalled — modelscope is replacing 9 corrupted shard files (dated Aug 1, 85MB-667MB each) one by one with ~3.4GB fresh downloads. Speed is 400kB/s-1.4MB/s per shard.

**Diagnosis:**
```bash
du -sh *.safetensors | sort -h | head -10
# Shows: 85M (model-00035), 98M (model-00039), 177M (model-00016), 200M (model-00037), ...
# All correct shards are 3.4-3.5GB. Too-small ones are leftover partials.
```

**Fix:** Kill all processes → delete ALL small shard files at once → restart. modelscope sees the missing files and immediately queues all 9 for parallel re-download at max speed (70MB/s-1.87GB/s):

```bash
# 1. Kill all processes
ssh ... "docker exec ... bash -c 'ps aux | grep \"modelscope download\" | grep -v grep | grep python | wc -l'"
# If count >= 1: kill via PID list

# 2. Delete all small/corrupt shard files
cd /home/public/models/deepseekv4-flash-0731/
rm -v model-00010-of-00048.safetensors \
      model-00013-of-00048.safetensors \
      model-00016-of-00048.safetensors \
      model-00029-of-00048.safetensors \
      model-00030-of-00048.safetensors \
      model-00031-of-00048.safetensors \
      model-00035-of-00048.safetensors \
      model-00037-of-00048.safetensors \
      model-00039-of-00048.safetensors

# 3. Verify count dropped
ls *.safetensors | wc -l
# Before: 47/48. After deletion: 38/48 (removed 9 small files)

# 4. Restart download immediately
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download ... --max-workers 8'"
# All 9 missing shards start downloading in parallel at high speed
```

**Result comparison:**
- Without deletion: 9 shards replaced one-by-one at 400kB/s-1.4MB/s each → ~6+ hours
- With deletion: all 9 shards re-queued immediately → first shards complete at 70-500MB/s → ~1-2 hours

**Key insight:** modelscope's "silently re-download corrupted shards in place" behavior (previously thought to be a feature, not a bug) is extremely slow for many corrupted shards. Deleting them manually triggers the fast parallel download path.

### 2. `ls | wc -l` going DOWN means cleanup, not failure

When `ls | wc -l` drops from 47 to 38 after `rm` of 9 small files — this is correct. The files were corrupt (wrong size) and should be removed. modelscope then re-downloads all 9. Do NOT panic when count decreases after `rm`.

### 3. Old PID 580247: survived SSH exit, blocked model-00011

PID 580247 was an old modelscope process from the previous session (started 16:24). It survived multiple SSH session exits (code 255) because it runs inside the container as a child of `docker exec`, which persists even when the SSH channel closes. It appeared alive via `ps aux` but held a stale `.incomplete` lock on model-00011 the entire ~6 hour session. `ps | wc -l == 1` was misleading — the process existed but was stalled, not downloading.

**Lesson:** Always kill ALL processes (`kill $(ps aux ... | awk "{print \$2}") 2>/dev/null`) AND verify count == 0 before restarting. A stale process is worse than a dead one because it silently holds `.incomplete` locks.

### 4. rm path must use FULL exact filename

```bash
# WRONG — truncates filename, silently does nothing:
rm -f model-00010.safetensors model-00013.safetensors ...
# → exit 0, "done", but 9 files still present

# CORRECT — full `-of-000YY.safetensors` suffix:
cd /home/public/models/deepseekv4-flash-0731/
rm -v model-00010-of-00048.safetensors model-00013-of-00048.safetensors ...
# → "removed 'model-00010-of-00048.safetensors'"
```

Always verify with `ls` or `wc -l` after rm.

### 5. model-00011 was NOT missing from disk — it completed

After PID 580247 was killed, a new process ran and completed model-00011 (3.4GB). The missing shard was caused by the stale lock, not a missing file. Deleting corrupt shard files was the fix, not re-running the full download.

### 6. SSH "Connection reset by peer" — keep submitting background checks

Server 192.168.12.12 frequently resets SSH connections when modelscope runs at high I/O. Pattern: keep submitting background `sleep N && ssh ...` commands with escalating delays — eventually one succeeds. Do NOT hammer with immediate retries.

## Download state at session end (2026-08-05 ~early morning)

After deletion + restart cycle:
- 36 safetensors confirmed on disk (~146GB)
- Process running: PID from proc_a4bc9e34d41f
- Active shards: model-00029 (88%, ~3.2GB), model-00001 (1%, ~9MB), model-00030 (~12GB), model-00016 (82%, ~2.7GB), model-00039 (~10.2GB), model-00045 (68%, ~690MB)
- ~12 shards still needed (40/48 at last check before deletion = 36 after rm, but process is re-downloading all missing ones)

## Remaining work

- Wait for all 12 missing shards to complete (expected: ~158GB, 48/48)
- After completion: verify with `ls | sort | grep 000` for no gaps
- Kill PID from proc_a4bc9e34d41f after done

## Commands used this session

```bash
# Kill all modelscope processes
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep \"modelscope download\" | grep -v grep | grep python | awk \"{print \$2}\" | xargs kill 2>/dev/null'"

# Delete all small/corrupt shard files
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'cd /home/public/models/deepseekv4-flash-0731/ && rm -v model-00010-of-00048.safetensors model-00013-of-00048.safetensors model-00016-of-00048.safetensors model-00029-of-00048.safetensors model-00030-of-00048.safetensors model-00031-of-00048.safetensors model-00035-of-00048.safetensors model-00037-of-00048.safetensors model-00039-of-00048.safetensors'"

# Start download
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && /opt/conda/envs/sw2_public/bin/modelscope download --model deepseek-ai/DeepSeek-V4-Flash-0731 --local_dir /home/public/models/deepseekv4-flash-0731/ --max-workers 8 2>&1'"

# Quick disk check
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/; ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# Shard file size check (find small/corrupt files)
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/*.safetensors | sort -h | head -10'"
```