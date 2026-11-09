# ModelScope Download: Persistent Lessons (2026-08-03 session)

## SSH Output Buffering — Authoritative Version

The previous documentation understated the severity. After this session, the real behavior is:

- modelscope `tqdm` progress lines are **line-buffered over the SSH pipe**
- When modelscope makes 8 parallel HTTP connections, each shard's progress is printed as a separate line
- Lines accumulate in the kernel pipe buffer; nothing reaches the local terminal until the buffer flushes
- In this session, the SSH channel process (`proc_95bf4eddafcc`) was confirmed **running for 43 minutes** with zero new output lines — only the initial 92-line conda error dump was visible
- `du -sh` confirmed the disk was growing the entire time (114GB → 115GB → 116GB)
- The buffering resolves when modelscope finishes or when a large batch of output fills the pipe

**Implications:**
- Do NOT conclude a download is "stuck" just because `proc log` shows no new lines with a running process
- Disk growth (`du -sh`) is the ONLY reliable real-time progress signal
- `uptime_seconds` growing on a background process = process is alive, not stuck
- If disk size unchanged for 5+ minutes AND process running AND network likely congested → network stall, kill and restart

**Buffer flush trigger**: When modelscope writes enough output to fill the pipe buffer (~65KB on Linux), all buffered lines appear at once. A single shard completing (1-10MB of output) often triggers the flush.

## Multiple-Process Pile-Up — Root Cause

Every `modelscope download` invocation creates a **new independent process**, regardless of whether a prior process is still downloading. modelscope does NOT detect existing downloads in the same directory.

The pile-up pattern is:
1. SSH drops → current background SSH process exits
2. Agent submits a new SSH command to restart download
3. Previous modelscope process in container is STILL RUNNING
4. New `docker exec` starts new modelscope process → now 2 processes
5. Repeat → 3, 4, 5+ processes

**The `pkill` approach from the SKILL.md is correct.** A one-liner:

```bash
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c \
    'pkill -f \"modelscope download\"; sleep 2; ps aux | grep \"modelscope download\" | grep -v grep | wc -l'"
```

**After pkill, modelscope cleans up partial shard files** for any shards it was actively downloading. This causes `du -sh` to show a smaller size after cleanup than before. For example: 108GB before kill, then after pkill + new download starts → back to ~99GB because partial shard .temp files were deleted. This is expected and correct behavior.

**Disk size regression pattern** (observed):
- Before kill: 108GB
- After kill: partial files cleaned → 99GB
- After new download starts: grows again
- This is NOT new download failing — it's stale partial files being removed

## Why `pkill` Over Targeted Kill by PID

Targeted PID kills (`kill 4137322`) were attempted multiple times. Problems:
- PID changes between restart cycles (hard to track which is "old" vs "new")
- When multiple processes exist, identifying the newest one requires `ps` parsing
- Human error: killed the wrong PID, leaving an old zombie running

`pkill -f "modelscope download"` is simpler and more reliable: it terminates ALL running download processes regardless of PID.

## Stale Background Process Notifications

When a long session runs, many background processes are started. These generate notifications after they exit (exit code 0 or 255). Most of these are **historical, not actionable**:
- Every `sleep 60 && ssh ...` generates an exit notification ~1 minute after it fires
- Notifications arrive in reverse chronological order (newest processes first)
- SSH-reset exits (exit code 255) are normal when 12.12 is overloaded

**Correct response**: Ignore exit notifications unless they contain a **size/shard/process-count result** (the actual data). Only the most recent `du -sh` + `ls *.safetensors | wc -l` result matters.

## Server Overload — Timing

12.12 enters SSH overload when:
- Multiple simultaneous SSH connections
- modelscope download creating high disk I/O
- Combined load exceeds sshd capacity

Recovery time: 5-15 minutes. During overload, ALL SSH attempts fail simultaneously.

**Correct strategy**: Always submit **multiple staggered checks** simultaneously with increasing delays (60s, 300s, 600s). This way, whichever one fires first gives the result. The "wait 5 minutes then try again" loop wastes time when the server is genuinely recovering.

## Session-Specific Download Data (2026-08-03 extended)

| Time | Size | Shards | Process State | Notes |
|------|------|--------|--------------|-------|
| 2026-08-03 early | 99GB | 46/48 | 2 procs (kill old) | proc_111c449a6b2e |
| 2026-08-03 | 100GB | 46/48 | PIDs 4038122+4112689+4112694 killed | |
| 2026-08-03 | 103GB | 46/48 | PID 4137322 continues | |
| 2026-08-03 | 105GB | 46/48 | 2 procs running (cleaned old) | |
| 2026-08-03 | 106GB | 46/48 | PIDs 4137322+4172409 both running | |
| 2026-08-03 | 107GB | 46/48 | PID 813 continues after kills | |
| 2026-08-03 | 108GB | 46/48 | PID 33704 runs (newest) | |
| 2026-08-03 | 109GB | 46/48 | PIDs 813+33704 both running, 813 killed | |
| 2026-08-03 | 110GB | 46/48 | PID 33704 only | |
| 2026-08-03 | 111GB | 46/48 | PID 33704 continues | |
| 2026-08-03 | 112GB | 46/48 | PID 33704 continues | |
| 2026-08-03 | 114GB | 46/48 | proc_95bf4eddafcc running 38min, no output | output buffered |
| 2026-08-03 | 115GB | 46/48 | Same proc, ~43min running | |
| 2026-08-03 | 116GB | 46/48 | SSH overload, disk check via background | |
| **~2h later** | **>116GB** | **>46** | **Still downloading** | 2 shards × 3.3GB remaining |

**Remaining work** (as of ~2h after last check): ~47GB, 2 shards (model-00006 + model-00009). ETA: 1-3 hours at typical speeds.

## Best Practice Checklist

Before starting or restarting a download on 12.12:
- [ ] `pkill -f "modelscope download"` — clean slate
- [ ] `ps aux | grep modelscope | grep -v grep | wc -l` → verify 0
- [ ] Start download: `ssh -T ... /opt/conda/envs/sw2_public/bin/modelscope download ... --max-workers 8`
- [ ] Submit staggered disk checks: `sleep 300 && ssh ... du -sh` AND `sleep 600 && ssh ... du -sh`
- [ ] Only rely on `du -sh` + `ls *.safetensors | wc -l` for progress, NOT process stdout
- [ ] If size unchanged for 10+ minutes with process alive → network stall, restart