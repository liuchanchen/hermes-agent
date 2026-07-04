# HF Download Log

## nvidia/GLM-5.1-NVFP4 (2026-06-03, 70.96)

- **Repo**: `nvidia/GLM-5.1-NVFP4` via `HF_ENDPOINT=https://hf-mirror.com`
- **Dest**: `/data/models/glm_5_1_nvfp4`
- **Total shards**: 49 × ~9.3 GB (tail shards 46-49: 3.6-5 GB each, normal for lm_head/embed)
- **HF_TOKEN**: NOT set — download still completed all 49 shards
- **Final size**: 434 GB

### Session 1 timeline (partial run, ~14:00-17:41)

| Time | Shards | Size | Event |
|------|--------|------|-------|
| ~14:00 | 23/49 | ~214 GB | Initial run, shards 01-23 REAL (9.31 GB each) |
| ~14:24 | 23/49 | ~215 GB | Stalled. Shards 24-31 = HTML errors (~1.5-1.7 GB, corrupt) |
| 17:30 | — | — | Deleted corrupt shards 24-31. Cleaned cache. Restarted |
| 17:41 | 25/49 | ~235 GB | New shards 24+25 confirmed REAL (9.4 GB each) |

### Session 2 (17:41-~18:46, died at 30/49)

| Time (CST) | Shards | Size | Event |
|------------|--------|------|-------|
| 18:46 | 30/49 | 319 GB | Process died (CAS URL expiry) |

### Session 3 (18:47-~20:09, died at 30/49)

Stalled at 30/49, restarted.

### Session 4 — final run (20:10-21:32, COMPLETE)

| Time (CST) | Shards | Size | Event |
|------------|--------|------|-------|
| 20:10 | 34/49 | 317 GB | Restarted after clean cache |
| 20:40 | 38/49 | 359 GB | +4 |
| 20:50 | 40/49 | 375 GB | +6 |
| 21:05 | 42/49 | 396 GB | +2 |
| 21:15 | 44/49 | 419 GB | +2 |
| 21:25 | 46/49 | 425 GB | +2 |
| 21:30 | 48/49 | 432 GB | +2 |
| **21:32** | **49/49** | **434 GB** | **COMPLETE** |

### Key lesson (corrected)

**HF_TOKEN was NOT required.** `nvidia/GLM-5.1-NVFP4` completed all 49 shards without it.
The HTML error pages in session 1 (shards 24-31 at ~1.5-1.7 GB) were from CAS URL expiry
on a stalled run — not from missing auth. Fresh restart resolved it.

**CAS URL expiry is the real failure mode:** hf-mirror.com's XetHub CAS signed URLs expire
every ~2-4 hours. Download dies silently (size stops growing, process may still show alive).
Fix: kill + `rm -rf .cache/huggingface/` + restart. Auto-resume fills the gap.

**Monitor rule:** check shard sizes every ~2 hours. Any shard < 5 GB for this model is suspect
(except shards 46-49 which are legitimately 3.6-5 GB for lm_head/embed tail layers).

### Shard size detector

```python
import os, glob
for f in sorted(glob.glob('/data/models/glm_5_1_nvfp4/model-*-of-*.safetensors')):
    gb = os.path.getsize(f)/1024/1024/1024
    print(('SMALL' if gb < 5 else 'OK') + f' {os.path.basename(f)}: {gb:.2f} GB')
```