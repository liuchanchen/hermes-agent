# ModelScope Download — 2026-08-04 Late Evening Session

## Key discoveries (new this continuation)

### 1. SSH channel exit discards in-progress shard data
After proc_d40dfcb1b746 exited (SSH code 255), `du -sh` regressed 152GB → 150GB. modelscope appears to delete `.incomplete` shards when the SSH channel closes abnormally — every SSH drop while shards are mid-download costs 1-4GB of progress. Previous assumption ("SSH drop is harmless, container process survives") was **incorrect for in-progress shards**.

Evidence:
- proc_d40dfcb1b746 running at 70MB/s-1.87GB/s for 11+ min, SSH dropped
- Next `du -sh`: 152GB → 150GB (−2GB)
- Old PID 580247 still running inside container

**Implication:** When only 1-2 shards remain, reduce `--max-workers` to 1-2 to minimize in-flight data, and keep the SSH session alive.

### 2. Old process survived 6+ hours with minimal CPU
- PID 580247: started 16:24, still running at 22:24
- Total CPU: 1.9 min over 6 hours — appeared mostly idle
- But held `.incomplete` lock on model-00011 the entire time
- `ps | wc -l == 1` was misleading — process existed but was stalled
- `ps aux | grep python` (with `grep -v grep`) showed this PID but no output from new process could reveal it was stale

**Lesson:** Process count == 1 is insufficient. Always verify with `du -sh` over 5-10 min windows. A process with 0 disk growth over 10 min is stalled even if `ps` shows it alive.

### 3. Two processes co-existing silently without errors
- PID 580247 (old, stalled) + new PID ran together
- New process completed most shards normally (disk growing, count increasing)
- Old process blocked model-00011 under its stale lock
- No error messages from either process
- Result: model-00011 never reached disk

**Lesson:** Always kill ALL processes before restarting. `kill $(ps ... | awk ...)` for ALL PIDs, then verify count == 0.

### 4. rm path truncation silently does nothing
```bash
# WRONG (truncated path, no -of-000YY suffix):
rm -f ...model-00010.safetensors ...model-00013.safetensors ...
→ exit 0, "done", but 9 files still present (files named model-00010-of-00048.safetensors etc.)

# CORRECT (full exact filename):
cd /home/public/models/deepseekv4-flash-0731/
rm -v model-00010-of-00048.safetensors ...
→ "removed 'model-00010-of-00048.safetensors'"
```
Verify deletion with `ls` or `wc -l` after rm.

## Active download state (session end, 2026-08-04 ~22:24)

Started via proc_d40dfcb1b746. SSH channel dropped but container process continues.

Active shards:
| Shard | Current | Target | Speed |
|-------|---------|--------|-------|
| model-00017 | 16.0GB | 3.32GB | 160-971kB/s |
| model-00010 | 11.6GB | 3.34GB | 196-826kB/s |
| model-00029 | 5.74GB | 3.32GB | 514-531kB/s |
| model-00033 | 8.04GB | 3.32GB | 142-185kB/s |
| model-00035 | 4.77GB | 3.32GB | 407-526kB/s |
| model-00011 | 9.27GB | ~3.3GB | 181-633kB/s |

Disk: 150GB, 38 safetensors. Expected: 158GB, 48 safetensors.

## Remaining work
- Wait for model-00011 to complete (~3.3GB remaining at 180-600kB/s → ~90 min)
- Wait for remaining 5 shards to complete
- Verify 48/48 safetensors, ~158GB total
- Kill PID 580247 before final verification