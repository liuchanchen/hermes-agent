# modelscope-download-2026-08-04.md

## Session: DeepSeek-V4-Flash-0731 download to 192.168.12.12

### Key events

**Bug: rm path truncation silently does nothing**
- Tried: `rm -f /home/public/models/deepseekv4-flash-0731/model-00010.safetensors ...` (glob pattern, no `-of-000YY` suffix)
- Result: exit 0, "done", but 9 files still present
- Fix: use full exact name `rm -v model-00010-of-00048.safetensors`, then `ls | wc -l` verify

**Bug: stale process holds .incomplete lock silently**
- Old PID 437117 (5+ min CPU time) appeared alive via `ps aux | wc -l == 1`
- New PID 517059 started alongside
- Both competed for the same shards; model-00011 never downloaded despite disk growing
- Fix: kill ALL processes before restart (`kill 437117 517059`)

**modelscope cleanup phase (disk growth without shard count increase)**
- After restart with 47/48 shards: `du -sh` grew 144→146→148→150GB but `ls | wc -l` stayed 47
- `ls -la` revealed 9 corrupted shard files (85MB–667MB, dated Aug 1) alongside correct 3.4GB ones
- modelscope was deleting small files AND re-downloading them in parallel
- `ls | wc -l` stayed 47 because deleted count == newly created count
- Correct behavior — waited without killing or restarting

**After cleanup phase: model-00011 still missing**
- 25 normal shards (3.4GB each) + 5 in-progress (1-2GB each) + 9 deleted small files = 39 files
- Expected 48 files total
- modelscope hadn't yet queued model-00011 for download
- Fix: killed all processes → waited → manually `rm -v` each small file with FULL filename → restarted download → model-00011 started immediately

### File inventory (after rm of 9 small files, before final restart)

| Pattern | Count | Size |
|---------|-------|------|
| Normal | 31 | 3.4–3.5GB |
| In-progress | 5 | 1.0–2.1GB |
| Deleted (rm -v) | 9 | 85MB–667MB, dated Aug 1 |
| Missing | 3 (model-00011 + 2 others) | — |
| **Total** | **48** | **~149GB** |

### Final restart output (proc_d40dfcb1b746)

```
Downloading [model-00017-of-00048.safetensors]:  78%|...| 2.61G/3.32G [00:19<00:00, 1.10GB/s]
Downloading [model-00029-of-00048.safetensors]:  73%|...| 2.44G/3.32G [00:19<00:00, 1.87GB/s]
Downloading [model-00010-of-00048.safetensors]:  60%|...| 2.01G/3.34G [00:19<00:06, 218MB/s]
Downloading [model-00020-of-00048.safetensors]:  51%|...| 1.72G/3.34G [00:19<00:08, 205MB/s]
Downloading [model-00021-of-00048.safetensors]:  81%|...| 2.69G/3.32G [00:19<00:00, 1.33GB/s]
```
Speed restored to normal after corrupted file cleanup. model-00011 download begun within first 60s.

### SSH server states observed

| State | Symptom | Action |
|-------|---------|--------|
| Normal | `ssh ... echo ok` → exit 0 | proceed normally |
| Overloaded | `kex_exchange_identification: read: Connection reset by peer` | wait 5min, retry |
| Recovering | one `sleep 600` succeeds | use that window immediately |
| Fully recovered | immediate SSH succeeds | check state NOW |