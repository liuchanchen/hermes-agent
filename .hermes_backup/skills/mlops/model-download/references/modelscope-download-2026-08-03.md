# ModelScope Download — 2026-08-03 Session (DeepSeek-V4-Flash-0731 on 192.168.12.12)

## Key New Learnings

### Old processes lock shards — always kill before restart
modelscope creates `.incomplete` lock files for shards in progress. Two concurrent processes block each other on the same shards. A new process will skip shards that have `.incomplete` locks from the old process, even though those shards haven't finished. Result: missing shards (model-00011 and model-00019 in this session) even when both processes appear to be running and disk is growing.

**Lesson:** Kill ALL old processes before starting a new download. `killall` or `kill $(ps ... | awk ...)` with `$2` extraction. Do not rely on process count alone — disk growth is the only reliable signal.

### Stalled process pattern
- `ps aux | grep "modelscope download" | wc -l` == 1 (process running)
- `du -sh` unchanged for 10+ minutes
- **Action:** Kill and restart immediately. Do not wait. Stalled processes do not recover on their own.

### Accurate kill command
```bash
ssh jianliu@192.168.12.12 "docker exec jianliu_sw2_public_19255 bash -c 'kill $(ps aux | grep \"modelscope download\" | grep -v grep | grep python | awk \"{print \$2}\") 2>/dev/null'"
```
Grep for `modelscope download` + `grep python` to avoid matching stray grep processes. awk `{print $2}` gets the PID column.

### Completion check: list missing shards
Do not trust shard count alone. When count == expected but download hasn't finished, list all shard numbers and diff against expected:
```bash
ls *.safetensors | sort  # check for gaps in numbering (e.g., 00011 and 00019 missing)
```

### Corrupted partial shard files block re-download
When inspecting `ls -la` output of the model directory, found:
```
-rw-r--r--   1 jianliu jianliu  184549376 Aug  1 04:03 model-00016-of-00048.safetensors
```
- **Actual size:** 184MB (should be ~3.5GB)
- **Date:** Aug 1 (4 days before download started on Aug 3) — clearly a leftover partial
- modelscope saw the file exists → skipped re-download
- But file is too small → shard is effectively missing

**Always verify shard sizes after completion:**
```bash
ls -la /home/public/models/<model>/*.safetensors | awk '$5 < 2000000000 {print}'
```
Any shard under 2GB is suspicious and should be deleted before re-download.

## New Learnings (2026-08-03 update — part 2)

### Stale lock, single-process, missing shard — the most dangerous failure mode
Even with `ps | wc -l == 1` (single process) and disk growing, specific shards can be silently skipped. The stuck process appears alive via `ps` (has CPU time) but is blocked waiting on I/O or a network issue. It holds `.incomplete` locks that cause the new process to skip those shards entirely. The disk growth from OTHER shards completing masks the missing one.

**Exact sequence (2026-08-03 real case):**
1. PID 437117 started ~13:33, ran for 5+ minutes of CPU time, held lock on model-00011
2. PID 437117 stalled (disk growth stopped) but `ps` still showed it running
3. New process started — saw `.incomplete` lock on model-00011 → skipped it
4. New process completed all OTHER 47 shards → disk grew to 151GB, count = 47
5. model-00011 never appeared across multiple restarts because the stale lock persisted

**Why `ps | wc -l == 1` is NOT a green light:**
A stuck process looks identical to a running one in `ps`. It consumes CPU (5 min was observed) but doesn't produce disk growth. The safe check is `du -sh` over 10+ minutes — if it hasn't changed, the process is stalled even if `ps` says it's alive.

**Always kill ALL processes before restart. Process count alone is insufficient.**

### Shard cleanup phase: disk grows, count stays flat — this IS progress
When modelscope finds a corrupted shard file (e.g., 184MB dated Aug 1 instead of ~3.5GB dated today), it deletes the bad file and re-downloads. During this phase:
- `du -sh` grows (net: -184MB + ~3.5GB = +~3.3GB)
- `ls | wc -l` stays flat (file replaced, not added)
- Looks like a stall in monitoring output

**Detection:**
```bash
ls -la *.safetensors | awk '$5 < 2000000000'
# model-00016: 184MB (Aug 1) ← leftover partial
# model-00013: 487MB (Aug 1) ← leftover partial
# model-00010: 353MB (Aug 1) ← leftover partial
# Correct files: ~3.4-3.5GB, Aug 3
```

**During cleanup: do NOT kill and restart.** The missing shard (e.g., model-00011) will be downloaded after all corrupted shards are replaced. Just wait.

**If missing shard still absent after cleanup completes:**
1. Kill all processes
2. Wait 5 minutes (for locks to expire)
3. `rm model-00011-of-00048.safetensors` (delete the corrupted or partial file)
4. Restart download

## Progress Log

| Time | Size | Shards | Process | Notes |
|------|------|--------|---------|-------|
| 05:28 | — | — | PID 813 | Initial download started |
| ~1h | 111GB | 46/48 | 1 | Multiple shards @72-90% |
| ~2h | 131GB | 47/48 | 1 | model-00019 done; model-00011 missing |
| ~3h | 140GB | 46/48 | 0 | Process exited; 00011+00019 stuck |
| ~3.5h | 140GB | 46/48 | 1 | PID 437117 stuck (no disk growth, 5min CPU) |
| ~4h | 141GB | 46/48 | 2 | Stuck proc + new proc competing |
| ~4.5h | 143GB | 47/48 | 1 | 00019 re-downloaded after cleanup |
| ~5h | 146GB | 47/48 | 1 | Cleanup: replacing bad shards (00016: 184MB→3.5GB) |
| ~5.5h | 151GB | 47/48 | 1 | Cleanup continues; 00011 pending after |
| ~6h | 150GB | 47/48 | 1 | Session end; 00011 pending |

## Final Status
- **47/48 shards** confirmed complete
- model-00019 ✅ (~6.4GB, Aug 3 14:08)
- **model-00011 still downloading** — expected after cleanup completes (~3.4GB)
- **Expected total:** ~158GB, 48 safetensors
- SSH buffering: zero output for 10-60min is NORMAL. `du -sh` is the only real-time progress signal.
- **Key lesson:** Process count == 1 + disk growing = likely fine. BUT: check `du -sh` over 10+ min. If disk hasn't changed, process is stalled even if `ps` says it's alive.
- **Key lesson:** SSH exit 255 is expected when the download process is running inside the container. The container process survives the SSH channel drop.
- **Key lesson:** Always kill ALL processes before restarting. Two processes = `.incomplete` lock conflicts = missing shards.
- **Key lesson:** Verify completion with `ls *.safetensors | sort` — `wc -l == N` is not enough; model-00011/00019 commonly skipped under stale locks.
- **Key lesson:** `du -sh` growing + `ls | wc -l` flat = shard cleanup in progress, NOT a stall. Do NOT kill during cleanup phase.