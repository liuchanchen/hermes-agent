---
name: model-download
description: Download ML models from ModelScope, HuggingFace, or via rsync/relay — SSH, Docker exec, container restart resilience, and process management patterns.
version: 0.1.0
author: Hermes Agent
license: MIT
---

# Model Download

Umbrella skill for downloading model weights from any source to remote GPU servers. Covers ModelScope, HuggingFace (via mirror), and relay/rsync patterns. Designed for large models (~100-700GB) where downloads take hours and SSH sessions drop.

## Quick Reference

| Source | Skill to Load |
|--------|--------------|
| HuggingFace (hf-mirror.com) | `huggingface-mirror-download` |
| ModelScope | This skill (`model-download`, references section below) |
| rsync / relay (no internet) | `huggingface-mirror-download` |

## ModelScope Download

For models on `modelscope.cn` (e.g. DeepSeek-V4-Flash-0731). Reference: `references/modelscope-download.md`

### Canonical Command

Inside the Docker container that has modelscope installed:

```bash
export MODELSCOPE_ENDPOINT=https://www.modelscope.ai
/opt/conda/envs/sw2_public/bin/modelscope download \
  --model deepseek-ai/DeepSeek-V4-Flash-0731 \
  --local_dir /home/public/models/deepseekv4-flash-0731/ \
  --max-workers 8
```

### Key Constraints

- **No `--force` flag** — modelscope CLI does NOT support `--force`. Using it causes silent failure. The CLI auto-resumes from incomplete shards.
- **`--local-dir` implies resume** — no separate resume flag needed. Interrupt and re-run to resume.
- **`--max-workers 8`** — parallel workers. Default 8. Use fewer on slow connections.
- **modelscope binary location** — not always in `$PATH`. On WarpDrive servers, check `/opt/conda/envs/sw2_public/bin/modelscope` inside Docker containers.

### Target Path Pattern

The `--local-dir` target should be a **host-mounted path** so files land on the host filesystem directly:

```
--local_dir /home/public/models/<model-name>/
```

If the container doesn't mount the host's model directory, verify the mount point first.

### Process Management: SSH Drops Don't Kill Downloads

The modelscope process runs **inside the Docker container** as a child of `docker exec`. When the SSH channel (the outer `ssh ... docker exec ...`) exits with code 255, the modelscope process inside the container **continues running**. This is correct and desired behavior.

**Verification after SSH drop:**
```bash
# Check if modelscope is still running inside the container
ssh -o ConnectTimeout=120 jianliu@<server> \
  "docker exec <container> bash -c 'ps aux | grep modelscope | grep -v grep | wc -l'"

# Check disk progress (safe to do anytime)
ssh -o ConnectTimeout=120 jianliu@<server> \
  "docker exec <container> bash -c 'du -sh /home/public/models/<model>/; ls /home/public/models/<model>/*.safetensors 2>/dev/null | wc -l'"
```

**Monitor pattern:** `du -sh` + safetensor shard count. Total expected count from ModelScope model page.

### Multiple Concurrent Processes: Kill Old Ones First

When restarting a download (e.g., after SSH drops), old modelscope processes may still be running inside the container. Multiple processes compete for resources and cause slowdowns. **Always check and kill before restarting:**

```bash
# Step 1: Find running modelscope processes
ssh -o ConnectTimeout=120 jianliu@<server> \
  "docker exec <container> bash -c 'ps aux | grep \"modelscope download\" | grep -v grep | grep python'"

# Step 2: Kill ALL of them before starting a new download
ssh -o ConnectTimeout=120 jianliu@<server> \
  "docker exec <container> bash -c 'kill \$(ps aux | grep \"modelscope download\" | grep -v grep | grep python | awk \"{print \\$2}\") 2>/dev/null; sleep 2; ps aux | grep \"modelscope download\" | grep -v grep | grep python | wc -l'"
# Verify count == 0 before proceeding

# Step 3: Start ONE new download
ssh -o ConnectTimeout=120 jianliu@<server> \
  "docker exec <container> bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download ...'"
```

**Why kill ALL before restarting, not just to consolidate?**
modelscope uses file-level locking (`.incomplete` files) for shards being downloaded. When two processes both run, they block each other on the same shards — neither completes. A new process will correctly skip already-downloaded shards, but will also skip shards that the old process has `.incomplete` locks on. Result: **missing shards even though disk is growing and process count is 1**. This is the most dangerous failure mode: the agent sees "disk growing, process running, everything fine" while specific shards are silently skipped.

**Exact symptoms of `.incomplete` lock conflict:**
- `ls *.safetensors | wc -l` reaches N-2 or N-1 but stalls (e.g. 47/48 instead of 48/48)
- `du -sh` continues growing (other shards completing) but the missing shards never appear
- `ps aux | grep modelscope | wc -l` == 1 — no obvious duplicate process
- `ls *.safetensors | sort` reveals specific shard numbers missing (commonly model-00011, model-00019)
- New restarts of modelscope also don't pick up the missing shards

**Also watch for corrupted partial shard files.** Old/damaged safetensor shards (e.g. 184MB instead of ~3.5GB, dated from days ago) look like "already downloaded" and block new downloads of the same shard. modelscope does NOT validate file sizes on resume — it only checks for the `.safetensors` extension and the `.incomplete` lock. If a shard file exists but is the wrong size, it will silently block that shard. Always verify final file sizes:

```bash
# Check for suspiciously small shard files (wrong size = corrupted/incomplete)
ls -la /home/public/models/<model>/*.safetensors | awk '$5 < 1000000000'
# A 184MB file dated Aug 1 when download started Aug 3 is a leftover partial
# modelscope ignores it but the too-small file blocks re-download under a stale .incomplete lock
```

**If shards are missing despite disk growing:** Kill all processes, wait 5 minutes, delete the corrupted partial file, restart.
**Kill all old processes first, then restart.**

**NEW — Stale .incomplete Lock: Missing Shard With Single-Process Appearance**

A critical failure mode discovered 2026-08-03: even with exactly 1 modelscope process running and disk growing, specific shards can be silently skipped. This happens when:

1. Process A (old, stuck) has an `.incomplete` lock file on shard N
2. Process A is stuck but `ps | wc -l` shows 1 (process exists, looks alive)
3. Process B (new) starts and sees the `.incomplete` lock → skips shard N
4. Process B completes all OTHER shards (disk grows, count increases toward N-1)
5. Shard N is never downloaded: `ls | wc -l` stalls at N-1 or N-2

**The deadly symptom:** `du -sh` grows, process count is 1, everything looks fine, but a specific shard number never appears. The new download process never picks it up on restart because the stale `.incomplete` lock is still on disk.

**Exact symptoms:**
- `ls *.safetensors | wc -l` reaches N-2 or N-1 but stalls (e.g. 47/48 instead of 48/48)
- `du -sh` continues growing (other shards completing) but the missing shards never appear
- `ps aux | grep modelscope | wc -l` == 1 — no obvious duplicate process
- `ls *.safetensors | sort` reveals specific shard numbers missing (e.g. model-00011, model-00019)
- New restarts of modelscope also don't pick up the missing shards

**Diagnosis:**
```bash
# Find corrupted/shard files by size (too small = leftover partial)
ls -la /home/public/models/<model>/*.safetensors | awk '$5 < 2000000000'

# Per-file size check
du -sh /home/public/models/<model>/*.safetensors | sort -h

# Find .incomplete lock files
find /home/public/models/<model>/ -name "*.incomplete" -type f

# List all shard files to find gaps
ls /home/public/models/<model>/*.safetensors | sort
```

**Fix:** Kill ALL processes → wait 5 min → delete the corrupted shard file → restart download:
```bash
ssh ... "docker exec <container> bash -c 'kill \$(ps aux | grep \"modelscope download\" | grep -v grep | awk \"{print \$2}\") 2>/dev/null'"
sleep 300
ssh ... "docker exec <container> bash -c 'rm -f /home/public/models/<model>/model-00011-of-00048.safetensors'"
ssh ... "docker exec <container> bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download ...'"
```

**Prevention:** Always kill ALL old processes before restarting a download. A stuck process that looks alive via `ps` is worse than a dead one because it silently holds `.incomplete` locks.

**Stalled download pattern — process exists but disk not growing:**
If `ps aux | grep "modelscope download" | wc -l` shows 1+ processes but disk size hasn't changed in 10+ minutes, the process is stuck. Kill it and restart immediately. Do NOT wait indefinitely. A stuck process looks identical to a running one via `ps` — disk growth is the only reliable progress signal.

### SSH Host Conda Error (Background Noise)

The host's `~/.bashrc` contains broken miniconda config that fires `An unexpected error has occurred. Conda has prepared the above report` on every SSH login. This is **harmless** — it comes from the host shell, not from the docker exec command. Ignore it. The actual download output follows after this block.

Workaround: use `ssh -T` to bypass the host shell activation, but `ssh` alone with `docker exec` also works (the docker exec output appears after the conda error noise).

### SSH Output Buffering: The #1 Monitoring Pitfall

**This is the most important pattern for this skill.** The modelscope process running over SSH (`ssh ... docker exec ... modelscope download ...`) has its **stdout fully buffered** by the SSH/pseudo-tty layer. The background process shows as "running" (`status: running`, `uptime_seconds: NNNN`) but produces **zero output lines** for 10–60 minutes at a stretch. Then a burst of progress lines appears at once (a "buffer flush"). This is NOT a download stall — the process is running normally inside the container.

**Consequences of misreading this:**
- Agent sees "running, no output" → assumes the process is stuck → kills it → loses partial progress
- Agent waits for download stdout to update → stalls the whole session
- Agent sees process exited with code 255 → panics and reports failure → even though download continued inside container

**The only reliable progress signal is independent disk checks.** Submit them as background processes with `sleep N` delays so they fire after the buffer flushes. Never wait for download stdout to update. Use `process poll` only to confirm the process hasn't crashed/exited — do not use it for progress visibility.

**Stalled vs. buffered — how to tell the difference:**
| Signal | Buffered (normal) | Stalled (kill + restart) |
|--------|-------------------|--------------------------|
| process status | running | running |
| output log | no new lines for 10–60 min | no new lines for 10–60 min |
| `du -sh` | grows slowly (~1GB/5min) | unchanged for 10+ min |
| disk growth | yes | no |
| **Action** | wait, schedule disk checks | kill and restart |

**Always submit disk checks proactively — do not wait for download output:**
```bash
# Schedule multiple checks at different times; they survive SSH drops
sleep 60  && ssh ... du -sh ... ls | wc -l   # fires in 1min
sleep 300 && ssh ... du -sh ... ls | wc -l   # fires in 5min (schedule both)
sleep 600 && ssh ... du -sh ... ls | wc -l   # fires in 10min (schedule all three)

# While waiting for buffer flush, also check process state independently
ssh ... "docker exec <container> bash -c 'ps aux | grep modelscope | grep -v grep | wc -l'"
# If count == 0 after download started, the process died — restart immediately
# If count == 1 and disk growing, everything is fine
```

**When to kill and restart despite a running process:**
1. Disk size unchanged for 15+ minutes while process is running
2. `ls *.safetensors | wc -l` hasn't changed in 15+ minutes
3. Process count dropped to 0 (crashed) — restart immediately
4. Process is running but shows no output AND disk not growing for 10+ minutes

### Server Overload: SSH "Connection reset by peer" Pattern

192.168.12.12 becomes unreachable when:
1. The modelscope download is running at high speed (heavy disk I/O + network)
2. Multiple concurrent SSH connections pile up

When this happens, **all SSH attempts fail with** `kex_exchange_identification: read: Connection reset by peer` or `Connection closed by 192.168.12.12 port 22`.

**Pattern:** Keep submitting background check commands with escalating delays (e.g. `sleep 60`, then `sleep 300`, then `sleep 600`) — eventually one will succeed. Do NOT keep hammering with immediate retry attempts. Use:

```bash
# Schedule checks with growing delays via background processes
sleep 60 && ssh ... du -sh ...   # fires in 60s
sleep 300 && ssh ... du -sh ...  # fires in 5min (schedule both)
sleep 600 && ssh ... du -sh ...  # fires in 10min (schedule all three)
```

### Docker exec vs Host Aliases

Some servers define aliases like `dkexec` in `~/.bash_alias` to run docker exec more easily. These aliases may not exist on all servers — always fall back to `docker exec <container> bash -c '<command>'` directly. On 192.168.12.12, `~/.bash_alias` does NOT exist; use `docker exec` directly.

### Disk Growth Without Shard Count Increase: Shard Cleanup Pattern

A NEW failure mode: `du -sh` grows but `ls *.safetensors | wc -l` stays flat. This means modelscope is **replacing corrupted/incomplete shard files** with fresh downloads. The old partial files (e.g., 184MB instead of ~3.5GB) are being deleted and re-downloaded.

**How to detect:**
```bash
# Old files (dated days ago, suspiciously small) indicate cleanup in progress
ls -la /home/public/models/<model>/*.safetensors | awk '$5 < 2000000000'
# Shows: model-00016 (184MB, Aug 1), model-00013 (487MB, Aug 1) vs. correct files (~3.5GB, today)
```

**Per-file size check:**
```bash
du -sh /home/public/models/<model>/*.safetensors | sort -h
# Lists all shards by size; too-small ones are leftover partials
```

**Key insight:** During this phase, the download is working correctly — it found the old corrupted shards and is replacing them. The missing shard (e.g. model-00011) will be downloaded after cleanup of all corrupted shards. **Do NOT kill and restart.** Just wait. The `ls | wc -l` count may actually go DOWN temporarily as modelscope removes the old small files before re-downloading them.

**Warning sign that actually means progress:**
- `du -sh` growing but `ls | wc -l` flat = modelscope replacing old bad shards ✓
- `du -sh` growing but `ls | wc -l` going down = modelscope deleting small corrupt files to re-download ✓
- `du -sh` flat AND `ls | wc -l` flat AND process count == 1 = **stalled**, kill and restart ✗

**If missing shard still not appearing after cleanup:**
- Kill ALL processes first (`kill $(ps aux | grep "modelscope download" | grep -v grep | awk "{print \$2}") 2>/dev/null`)
- Wait 2-5 minutes for stale `.incomplete` lock files to clear
- Delete the corrupted shard file: `rm -v /home/public/models/<model>/model-000XX-of-000YY.safetensors` (FULL filename with `-of-000YY.safetensors` suffix — not a glob)
- Restart download immediately — do not wait for SSH to settle; model-00011 download begins right after deletion

**Critical: rm path must be the exact full filename.** A truncated path like `rm model-00010.safetensors` silently does nothing (exit 0, no error, file still on disk) because the file is named `model-00010-of-00048.safetensors`. Always use the full path with shard index: `rm -v model-00010-of-00048.safetensors`. Verify deletion with `ls` or `wc -l` count before proceeding.

### Small/Tiny Shards Get Stuck Repeatedly (Tokenizers, Metadata)

DeepSeek-V4-Flash-0731's model-00045-of-00048.safetensors is only 0.99GB (a tokenizer or metadata file, vs ~3.4GB for weight shards). It repeatedly stalls at 40-68%, SSH exit deletes it, and the cycle repeats. **Fix:** `rm model-00045-of-00048.safetensors` then restart — modelscope re-downloads from 0 immediately. The file itself is the correct size (0.99GB), not corrupted — it just gets interrupted repeatedly by SSH drops.

**Pattern to watch for:** A shard that is significantly smaller than the others (e.g. <2GB vs ~3.4GB for the rest) and repeatedly fails to complete. Check `du -sh *.safetensors | sort -h` — the smallest shard is the one to delete and re-trigger.

### Exit Codes: 255 vs 1
- **exit code 255** = SSH channel dropped (normal, modelscope continues inside container)
- **exit code 1** = modelscope hit a retry error on tokenizer.json or other metadata (e.g. `ReadTimeoutError: HTTPSConnectionPool(host='www.modelscope.cn', port=443): Read timed out`). Safetensor shards may still be complete. Check disk to verify.

### Completion Check

Download is complete when:
1. `ls *.safetensors | wc -l` == expected shard count (from ModelScope model page)
2. `du -sh` total size matches expected (~156GB for DeepSeek-V4-Flash-0731, accounting for any small tokenizer shards)
3. `ps aux | grep modelscope | wc -l` == 0 (no process running)
4. **`ls *.safetensors | sort` — verify no gaps** in shard numbering
5. **`du -sh *.safetensors | sort -h` — verify all shard sizes are in the expected range** (weight shards ~3.4-3.5GB; tokenizer/metadata shards ~0.5-1GB; anything between 0.5-2.5GB is corrupted/partial and must be deleted)
6. **`du -sh` did not regress** — if `du` shrank since last check, SSH exit deleted in-flight shards. Restart to recover.

### SSH Channel Exit Deletes In-Flight Shards & Causes `du` Regression
**Critical finding 2026-08-04/05:** SSH exit does NOT cleanly persist partial shard data. modelscope deletes ALL mid-download `.incomplete` shards on SSH channel exit (even clean exit, even if container process survives). `du -sh` can **regress** 1-4GB between checks.

**Why this is worse than previously documented:** The container process (`docker exec`) may still appear in `ps` after SSH drop — but its partial data was deleted. The process is running but has no shard data to continue from.

**Why workers matter:** `--max-workers 8` = 8 shards in-flight = up to ~24GB deleted per SSH exit. `--max-workers 1` = at most ~3GB at risk.

**Safest practice — especially when 1-4 shards remain:**
```bash
# When 1-4 shards remain, switch to --max-workers 1
ssh ... "docker exec ... bash -c 'export MODELSCOPE_ENDPOINT=... && /opt/conda/envs/sw2_public/bin/modelscope download --model ... --local_dir ... --max-workers 1 2>&1'"
```

**Symptom:** `du` shrinks between checks (e.g. 152GB → 149GB). The container process may still be running inside the container — but partial shards were deleted by the channel exit.

**Safest practice:**
- When 1-2 shards remain, restart download with `--max-workers 1` to minimize in-flight data
- Schedule disk checks via `sleep N` background processes — they survive SSH drops
- If `du` regressed after reconnection: kill the container process, restart download immediately (modelscope re-downloads deleted shards from scratch)
- Do NOT wait for "process looks healthy" — `ps` may show process alive even after it deleted partial data

**Why workers matter:** `--max-workers 8` means 8 shards download in parallel; an SSH exit at that moment deletes up to 8 × ~3GB of partial data. `--max-workers 1` means at most 1 partial shard at risk (~3GB max loss).

### Old Processes Live Hours With Minimal CPU
A modelscope process that ran 6+ hours with only 2 min total CPU (appeared mostly idle in `ps`) held a `.incomplete` lock on model-00011 the entire time. A process is stalled when `du -sh` shows no growth over 10+ minutes — even if `ps` shows it alive with CPU time. Always verify with `du -sh` windows, not process count alone.

### Restart After Container Restart

If the container was restarted, re-run the download command — modelscope skips already-downloaded shards automatically.

## rsync / Relay Pattern

For servers with no external internet access (e.g. 10.10.68.98):

```bash
# Step 1: Download to a machine with internet
hf download org/model --local-dir /local/path/to/model

# Step 2: Rsync to the target server
rsync -avP /local/path/to/model/ user@target:/data/models/model/

# Step 3: Clean up local copy
rm -rf /local/path/to/model/
```

Reference: `huggingface-mirror-download` skill for full details.

## References

- `references/modelscope-download.md` — detailed session notes, CLI help, speed observations
- `references/modelscope-download-2026-08-03.md` — initial discovery of stale `.incomplete` lock failure mode
- `references/modelscope-download-2026-08-04.md` — SSH process exit, container process persistence
- `references/modelscope-download-2026-08-04-late.md` — SSH channel exit deletes in-flight shards finding
- `references/modelscope-download-2026-08-05.md` — small shard bulk deletion accelerator
- `references/modelscope-download-2026-08-05-am.md` — rm path truncation bug, old PID survived hours SSH drops
- `references/modelscope-download-2026-08-05-pm.md` — `--max-workers 1` strategy, 6-hour-old PID with 2min CPU still holding lock
- `references/modelscope-download-2026-08-05-late.md` — model-00045 tokenizer shard (~1GB vs 3.4GB), exit code 1 = tokenizer timeout
- `references/models-we-use.md` — running log of models, paths, sizes
- `huggingface-mirror-download` skill — HuggingFace-specific patterns

## Pitfalls

- **No `--force`** — modelscope CLI does not support this flag. Re-running the command auto-resumes.
- **Multiple concurrent downloads** — always kill old processes before restarting. Competing processes cause severe slowdown and **missing shards due to `.incomplete` lock files**. Always kill all old processes; do not rely on `ps | wc -l` alone.
- **SSH exit 255 ≠ download failure, BUT discards in-progress shards** — the container process survives SSH drops, but any shards mid-download at the moment of exit are deleted by modelscope's channel exit. `du -sh` can regress 1-4GB. When 1-2 shards remain, use `--max-workers 1` to minimize in-flight data at risk.
- **Old processes appear alive via `ps` but are stalled** — a process running 6+ hours with only 2 min total CPU held a `.incomplete` lock on model-00011 the entire time. Process count == 1 is insufficient; always verify with `du -sh` over 5-10 min windows.
- **Disk check before download** — `df -h /home` on the target server before starting. Ensure enough free space.
- **modelscope not in PATH** — on WarpDrive Docker containers, use the full path `/opt/conda/envs/sw2_public/bin/modelscope`.
- **Verify no gaps in shard numbering** — `ls *.safetensors | sort` after completion. `wc -l == N` is not sufficient; stale `.incomplete` locks can silently skip specific shard numbers (e.g. model-00011, model-00019).
- **Verify shard sizes** — modelscope does NOT validate file sizes on resume. A 184MB leftover partial (wrong date, too small) silently blocks re-download of that shard. Check: `ls -la *.safetensors | awk '$5 < 2000000000'` — delete any under 2GB before re-downloading.
- **rm path truncation silently does nothing** — `rm model-00010.safetensors` (without the full `-of-000YY` suffix) succeeds with exit 0 but removes nothing. Always use `rm -v <full-exact-name>` and verify with `ls` or `wc -l` after.
- **Exit code 1 = tokenizer/metadata timeout, not safetensor failure** — modelscope exits code 1 when it hits a retry error on tokenizer.json or similar metadata files (e.g. `ReadTimeoutError`). Safetensor shards may still be complete. Check disk to verify.