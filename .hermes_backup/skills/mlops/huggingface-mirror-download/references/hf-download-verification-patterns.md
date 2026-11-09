# HF Download Verification Patterns

## The Lock File Pattern (Canonical Monitor)

When `hf download` runs via `setsid` in an SSH session, the SSH process may exit from the
process table even while HF's internal worker threads (forked by the venv's Python runtime)
are still actively downloading. **Process state is NOT a reliable indicator of download
activity. HF cache lock files ARE.**

HF stages downloads in `$LOCAL_DIR/.cache/huggingface/download/`:
- **`.lock` files** = active workers (one per shard being downloaded right now)
- **`*.incomplete` files** = partial downloads (stale if download died)
- After completion, the file moves to `$LOCAL_DIR/` and the lock disappears

### Verified Monitoring Pattern (2026-06-03, 70.96, nvidia/GLM-5.1-NVFP4)

```bash
# Pattern: poll every 5 min, capture shard count + total bytes + lock count
while sleep 300; do
  SHARDS=$(find /data/models/glm_5_1_nvfp4 -maxdepth 1 -name 'model-*.safetensors' | wc -l)
  SIZE=$(du -sh /data/models/glm_5_1_nvfp4/ | awk '{print $1}')
  LOCKS=$(find /data/models/glm_5_1_nvfp4/.cache -name '*.lock' | wc -l)
  echo "$(date +%H:%M:%S)  shards=$SHARDS/49  size=$SIZE  locks=$LOCKS"
done
```

### `setsid` Verification Log

| Timestamp | Shards | Size | Locks | Process Alive |
|-----------|--------|------|-------|---------------|
| 12:30 | 8/49 | 92GB | 7 | alive |
| 12:35 | 8/49 | 98GB | 7 | alive |
| 12:40 | 10/49 | 104GB | ? | alive |
| 12:45 | 10/49 | 109GB | ? | alive |
| 12:50 | 10/49 | 114GB | ? | alive |
| 12:55 | 11/49 | 119GB | ? | alive |
| 13:00 | 12/49 | 124GB | ? | alive |
| 13:05 | 13/49 | 128GB | ? | alive |
| 13:10 | 14/49 | 137GB | ? | alive |
| 13:15 | 15/49 | 143GB | ? | alive |
| 13:20 | 15/49 | 147GB | ? | alive |
| 13:25 | 16/49 | 160GB | ? | alive |
| 13:30 | 17/49 | 166GB | ? | alive |
| 13:35 | 18/49 | 179GB | ? | alive |
| 13:40 | 19/49 | 185GB | ? | alive |
| 13:45 | 19/49 | 191GB | ? | alive |
| 13:50 | 21/49 | 197GB | ? | alive |
| 13:55 | 21/49 | 224GB | 8 | alive |

**Key observations:**
1. SSH command that launched `setsid` timed out at 10s, but the `setsid` child survived
2. Process table showed the HF download PIDs for the first few checks, then they
   disappeared — but the download continued (confirmed by size growth and lock files)
3. Lock file count of 8 at 13:55 indicates 8 parallel workers active
4. Sustained rate: ~5-6 GB / 5 min (~18 MB/s) over 3.5 hours

### When to Restart

If lock files drop to 0 AND shard count hasn't changed in 30+ minutes, the download
has stalled. Check for stale `.lock` or `.incomplete` files:

```bash
# Check for stale locks (should be 0 if download is running or done)
find /data/models/<model>/.cache -name '*.lock' | wc -l

# Check for incomplete files:
find /data/models/<model>/.cache -name '*.incomplete' | wc -l

# If locks=0 but download not complete:
# 1. Kill any remaining hf download processes
# 2. Clean stale files:
rm -rf /data/models/<model>/.cache/huggingface/download/*.lock
rm -rf /data/models/<model>/.cache/huggingface/download/*.incomplete
# 3. Restart with setsid
```