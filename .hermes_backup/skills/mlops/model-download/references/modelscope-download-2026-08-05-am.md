# ModelScope Download Session Log — 2026-08-05 (Morning)

## Download Target
- Model: `deepseek-ai/DeepSeek-V4-Flash-0731`
- Server: 192.168.12.12, container `jianliu_sw2_public_19255`
- Path: `/home/public/models/deepseekv4-flash-0731/`
- Binary: `/opt/conda/envs/sw2_public/bin/modelscope`

## Session Summary
Continuation of previous sessions. Target had accumulated 47/48 shards with model-00011 missing. modelscope kept re-downloading old corrupted shards instead of downloading model-00011 due to stale PID 580247 holding a `.incomplete` lock.

## Key Findings This Session

### 1. Old PID Survived Hours of SSH Drops
- PID 580247 (old modelscope process, started ~16:24) survived multiple SSH exits overnight
- `ps aux` showed it running (1 process) even after hours of SSH disconnection
- CPU time: only 2:45 accumulated over ~6h runtime — it was mostly stalled
- It held a `.incomplete` lock on model-00011, blocking new processes from downloading it
- **A process can look alive via `ps` while being completely stalled**

### 2. rm Path Truncation Bug
- `rm model-00010.safetensors` (without the full `-of-000YY` suffix) succeeds with exit 0 but removes nothing
- File is named `model-00010-of-00048.safetensors` — the truncated path doesn't match
- Always use the full exact name: `rm -v model-00010-of-00048.safetensors`
- Verify with `ls` or `wc -l` after deletion

### 3. Small Shard Deletion Strategy (Massively Accelerates Completion)
When many shard files are corrupted/small (e.g. 184MB, 487MB, 574MB instead of ~3.5GB):

Instead of waiting for modelscope to replace them one-by-one:
```bash
# List all shards by size
du -sh /home/public/models/deepseekv4-flash-0731/*.safetensors | sort -h

# Delete ALL shards under ~2.5GB (corrupted/partial)
rm -v model-00001-of-00048.safetensors \
      model-00010-of-00048.safetensors \
      model-00013-of-00048.safetensors \
      model-00016-of-00048.safetensors \
      model-00021-of-00048.safetensors \
      model-00029-of-00048.safetensors \
      model-00030-of-00048.safetensors \
      model-00031-of-00048.safetensors \
      model-00033-of-00048.safetensors \
      model-00035-of-00048.safetensors \
      model-00037-of-00048.safetensors \
      model-00039-of-00048.safetensors \
      model-00045-of-00048.safetensors
# Then restart — modelscope starts ALL at once in parallel
```

This was applied around 11:00-12:00 on 2026-08-05:
- Deleted 9 small shards (10,13,16,29,30,31,35,37,39) → disk shrank ~5GB
- Restarted download → model-00029,31,35,10 completed quickly in parallel
- `ls | wc -l` jumped from 30→36→37→40→41 as multiple shards completed

**Effect:** Massive acceleration. Without deletion, modelscope replaces one small shard at a time (~400kB/s each, 20+ minutes per shard). With deletion + restart, all deleted shards start simultaneously at full speed.

### 4. modelscope Auto-Deletes Small Files on Resume
When modelscope restarts and detects a shard file is too small (old partial), it **deletes** the small file and re-downloads it. This causes:
- `du` to temporarily shrink (old partial deleted) then grow (new full file)
- `ls | wc -l` to temporarily decrease (old small file gone before new one appears)
- This is **normal and correct** — do NOT kill the process

## Disk Progression (2026-08-05 Morning)
| Time | GB | Files | Notes |
|------|-----|-------|-------|
| 09:50 | 140 | 46 | model-00011,19 missing |
| 10:00 | 144 | 47 | model-00019 appeared |
| 11:00 | 150 | 47 | PID 580247 blocking, rm small files |
| 11:10 | 149 | 36 | 9 small shards deleted |
| 11:20 | 146 | 36 | model-00029 ~88% |
| 11:30 | 147 | 36 | downloading |
| 12:00 | 150 | 37 | model-00031/29 done |
| 12:30 | 151 | 40 | model-00035/10/31/29 done |
| 13:00 | 152 | 41 | downloading |
| 13:30 | 153 | 41 | downloading |

## Process Count vs. Actual State
- PID 580247: `ps` alive, `du` flat for hours = **stalled, holding lock**
- PID 517059: duplicate new process competing
- After kill + restart: 1 process, `du` growing = **healthy**
- **Lesson:** `ps | wc -l == 1` is NOT sufficient proof of health. Always check `du -sh` over 5-10 min windows.

## Command Used This Session
```bash
export MODELSCOPE_ENDPOINT=https://www.modelscope.ai
/opt/conda/envs/sw2_public/bin/modelscope download \
  --model deepseek-ai/DeepSeek-V4-Flash-0731 \
  --local_dir /home/public/models/deepseekv4-flash-0731/ \
  --max-workers 8
```

## Still Missing Shards (as of 13:30)
model-00001, 00021, 00033, 00045 (too small, deleted but not yet re-downloaded)
Remaining gap: 48 - 41 = 7 shards (including these 4 + 3 others)