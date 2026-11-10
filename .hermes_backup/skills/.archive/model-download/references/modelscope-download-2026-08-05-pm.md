# ModelScope Download Session Notes — 2026-08-05 PM

## Session Context
Downloading DeepSeek-V4-Flash-0731 (48 safetensor shards, ~158GB) to container `jianliu_sw2_public_19255` at `/home/public/models/deepseekv4-flash-0731/` on server `192.168.12.12`.

## Key Findings

### 1. SSH Channel Exit Deletes In-Flight Shards (Critical)

**Previous assumption (WRONG):** SSH drop → container process survives → download continues harmlessly → just wait and reconnect.

**Actual behavior:** modelscope deletes ALL mid-download `.incomplete` shards on SSH channel exit. Result: `du -sh` can **regress** 1-4GB between checks. Container process may still show in `ps` but partial data is gone.

**Why workers matter:** `--max-workers 8` = up to 8 shards in-flight = up to ~24GB deleted on SSH exit. `--max-workers 1` = at most ~3GB at risk.

**When 1-4 shards remain, use `--max-workers 1`:**
```bash
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download --model ... --local_dir ... --max-workers 1 2>&1'"
```

### 2. modelscope Auto-Deletes Small Files on Resume (Good!)

modelscope automatically detects and deletes shard files that are too small (corrupted/partial) when resuming. This is self-healing.

**Evidence this session:** model-00016 (184MB, Aug 1), model-00013 (487MB, Aug 1) — old partial files vanished on restart, replaced by full-size downloads. `du` grew but `ls | wc -l` stayed flat because modelscope replaced files one-by-one.

**Check for small shards:**
```bash
du -sh /home/public/models/deepseekv4-flash-0731/*.safetensors | sort -h | head -10
# Anything < 2GB is a leftover partial
```

### 3. Small Shard Deletion = Massive Accelerator

Instead of letting modelscope replace one small shard at a time (slow), manually delete ALL small shards at once. modelscope then downloads all missing shards in parallel from the start.

**This session:** Deleted 9 small shard files at once (models 10, 13, 16, 29, 30, 31, 35, 37, 39). Restarted → `ls | wc -l` jumped 30→36 in one 10-min window.

**Commands:**
```bash
# Delete small shards — FULL filename with -of-NNNNN suffix
ssh ... "docker exec ... bash -c 'rm -v model-00010-of-00048.safetensors model-00013-of-00048.safetensors ...'"

# Verify deletion
ssh ... "docker exec ... bash -c 'ls *.safetensors | wc -l'"

# Restart download
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download ...'"
```

### 4. rm Path Truncation Bug

`rm model-00010.safetensors` (WITHOUT `-of-000YY` suffix) succeeds exit 0 but removes nothing. File is `model-00010-of-00048.safetensors`. Always use full exact filename.

### 5. Old Process Survived 6+ Hours with 2 min CPU

PID 580247 ran 6+ hours with only ~2:45 min total CPU. It held a `.incomplete` lock on model-00011 the entire time, silently blocking that shard even after new processes restarted.

**Lesson:** `ps | grep modelscope | wc -l == 1` is insufficient. Verify with `du -sh` over 5-10 min windows. Zero disk growth over 10 min = stalled even if `ps` shows alive.

## Session Progress Timeline

| Time | du (GB) | ls (files) | Note |
|------|---------|------------|------|
| ~16:00 | 149 | 36 | After deleting 9 small shards |
| ~16:10 | 150 | 37 | +1 file |
| ~16:20 | 151 | 40 | +3 files |
| ~16:30 | 152 | 41 | +1 file |
| ~16:40 | 152 | 43 | +2 files |
| ~16:50 | 152 | 43 | stalled (SSH down) |
| ~17:00 | 154 | 44 | recovered |
| ~17:10 | 154 | 44 | stalled |

## Session End State

154GB / 44/48 files. Still missing: model-00001 (1GB partial), model-00045 (1GB partial). 4 shards remaining: 01, 10, 45, +1 more.

## Verified Commands

```bash
# Kill old processes (verify count == 0)
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'ps aux | grep \"modelscope download\" | grep -v grep | grep python | awk \"{print \\\\$2}\" | xargs kill 2>/dev/null; sleep 2; ps aux | grep \"modelscope download\" | grep -v grep | grep python | wc -l'"

# Delete small shards
ssh ... "docker exec ... bash -c 'rm -v model-00001-of-00048.safetensors model-00045-of-00048.safetensors'"

# Restart download
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && /opt/conda/envs/sw2_public/bin/modelscope download --model deepseek-ai/DeepSeek-V4-Flash-0731 --local_dir /home/public/models/deepseekv4-flash-0731/ --max-workers 8 2>&1'"

# Disk check
ssh ... "docker exec ... bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/; ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'"

# Small shard detection
ssh ... "docker exec ... bash -c 'du -sh /home/public/models/deepseekv4-flash-0731/*.safetensors | sort -h | head -5'"

# When 1-4 shards remain (use --max-workers 1)
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download --model ... --local_dir ... --max-workers 1 2>&1'"
```