# Multi-Hop rsync: 70.88 → local → 70.92 (qwen_image_2512)

**Date:** 2026-06-08
**Model:** qwen_image_2512 (~54 GB)
**Source:** 10.10.70.88:/data/models/qwen_image_2512/
**Intermediate:** local WSL (`/home/jianliu/qwen_image_2512_dst/`)
**Destination:** 10.10.70.92 — **FILES NEVER ARRIVED** (see below)

## Why multi-hop

70.88 and 70.92 cannot reach each other directly:
- 70.88 → 70.92: `Permission denied (publickey,password)` — 70.92 doesn't have 70.88's pubkey
- Local machine already had SSH key accepted by both servers

## Step 1: 70.88 → local (SUCCEEDED)

```bash
rsync -avP --bwlimit=0 jianliu@10.10.70.88:/data/models/qwen_image_2512/ /home/jianliu/qwen_image_2512_dst/
```

- Duration: ~25 min for 57.7 GB at ~35-40 MB/s
- Phase 1 (metadata): fast but small
- Phase 2 (model shards): ~100 MB/s initially, slowed to ~5-15 MB/s in latter half
- rsync output: `sent 1,300 bytes received 57,718,695,455 bytes 39,331,309.54 bytes/sec total size is 57,704,601,558 speedup is 1.00`
- Verified: `du -sh /home/jianliu/qwen_image_2512_dst/` → 54GB ✅

## Step 2: local → 70.92 (FAILED — exit 0 but 0 bytes written)

### Attempt 2a: /data/models/qwen_image_2512/ (FAILED)

```bash
rsync -avP --bwlimit=0 /home/jianliu/qwen_image_2512_dst/ jianliu@10.10.70.92:/data/models/qwen_image_2512/
```
Error: `rsync: [Receiver] mkdir "/data/models/qwen_image_2512" failed: No such file or directory (2)`

**Root cause:** `/data/` on 70.92 is owned by `rapidsdb`, jianliu cannot write there:
```
$ ls -la /data/
drwxr-xr-x  5 rapidsdb rapidsdb  4096 May 20 16:36 .
drwxr-xr-x  3 rapidsdb rapidsdb  4096 May 20 17:26 rapidsdb
drwx------  2 rapidsdb rapidsdb 16384 May 12 11:47 lost+found
```
The error message ("No such file or directory") masked the actual permission-denied condition.

### Attempt 2b: /home/jianliu/qwen_image_2512/ (FAILED — silent exit 0)

```bash
rsync -avP --bwlimit=0 /home/jianliu/qwen_image_2512_dst/ jianliu@10.10.70.92:/home/jianliu/qwen_image_2512/
```

rsync output: `sent X bytes received Y bytes Z bytes/sec total size is 57,704,601,558 speedup is 1.00`
Exit code: **0 (SUCCESS)**. **BUT** `ssh jianliu@10.10.70.92 "du -sh /home/jianliu/qwen_image_2512/"` showed **0 bytes**. Files never arrived.

**Root cause: unknown.** Destination path was confirmed writable (`echo test > ~/.write_test` succeeded). No rsync error shown. This is the most dangerous rsync failure mode — success exit code with zero files transferred.

## Key lessons

1. **rsync can exit 0 but transfer 0 bytes silently.** Always verify with `du -sh` AND `ls` on remote immediately after rsync, even when exit code is 0. This is the most dangerous failure mode.

2. **`/data/` is rapidsdb-owned on ALL known servers (70.88, 70.92, 70.95, 70.96, 70.98)** — jianliu cannot write to `/data/` directly. Always default to `/home/jianliu/` when `/data/` is locked.

3. **rsync "mkdir failed: No such file or directory" can mean permission denied**, not just missing directory. Check ownership first: `ssh TARGET "ls -la /parent/path/"`.

4. **rsync cannot create missing parent directories** if the parent is not writable by the target user. Always pre-flight destination write access.

5. **Pre-create destination on remote** if needed:
   ```bash
   ssh jianliu@TARGET "mkdir -p /path/to/destination"
   ```
   If that fails (Permission denied), fall back to `$HOME/`.

6. **`ssh-copy-id` is non-interactive** — cannot be used from Hermes terminal; user runs it manually.

7. **Local SSH to target was already working** (jianliu@10.10.70.92 accepted our key). Only the 70.88 → 70.92 hop was blocked.

8. **SSH key is directional** — having A's SSH key on B doesn't mean B's SSH key is on A. `ssh-copy-id jianliu@10.10.70.92` from local works; `ssh jianliu@10.10.70.92` from 70.88 fails with Permission denied.

9. **`du -sh` on remote is the most reliable progress indicator** — rsync output can show stale snapshots while real transfer continues in background. Poll `du -sh /remote/dst/` every 1-2 min.

## Verification patterns before starting rsync

### Test SSH connectivity without interactive password prompt

```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes jianliu@10.10.70.XX "hostname"
```

`BatchMode=yes` forces key-only auth and fails immediately if key isn't accepted.

### Dry-run before real transfer

```bash
rsync -avP --dry-run /local/src/ jianliu@10.10.70.XX:/remote/dst/ 2>&1 | head -20
```

### Verify destination is writable before rsync

```bash
ssh jianliu@10.10.70.XX "mkdir -p /path/to/destination && echo WRITABLE || echo PERMISSION_DENIED"
```

If this fails (Permission denied), **fall back to `$HOME/` immediately** — do not waste time on a transfer that will error on mkdir.