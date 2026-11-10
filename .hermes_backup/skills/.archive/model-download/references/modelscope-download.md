# ModelScope Download: DeepSeek-V4-Flash-0731 Session Notes

Session: 2026-08-03. Target: 192.168.12.12, container `jianliu_sw2_public_19255`.

## Model
- **Repo**: `deepseek-ai/DeepSeek-V4-Flash-0731`
- **Page**: https://www.modelscope.cn/models/deepseek-ai/DeepSeek-V4-Flash-0731
- **Total**: 48 safetensor shards, ~156-159GB expected
- **Endpoint**: https://www.modelscope.ai (set via `MODELSCOPE_ENDPOINT` env var)

## Key Learnings

### `--force` flag does NOT exist
The modelscope CLI does not support `--force`. Using it causes silent failure. Verified via `--help` output. Auto-resume works by re-running the same command.

### modelscope binary location
Not in `$PATH` inside the container. Full path:
```
/opt/conda/envs/sw2_public/bin/modelscope
```

### modelscope --help output
```
modelscope download --help
Usage: modelscope download [OPTIONS]

  Download models or datasets from ModelScope

Options:
  --model TEXT               Model or dataset id, e.g. AI-ModelScope/llama2
  --model_revision TEXT      Revision of the model
  --dataset TEXT             Dataset id, e.g. AI-ModelScope/llama2
  --dataset_revision TEXT    Revision of the dataset
  --files TEXT               Specific files to download, separated by comma
  --local_dir TEXT           Local directory to save the file
  --cache_dir TEXT           Cache directory to save the file
  --ignore-file TEXT         Files to ignore
  --scope TEXT               Model scope
  --max_workers INTEGER     Max workers number, default 8
  --Revision TEXT            Revision of the model
  --help                     Show this message and exit
```
Note: NO `--force` option. NO `--resume` option.

### SSH host conda error (harmless)
Host's `~/.bashrc` fires this on every SSH login:
```
An unexpected error has occurred. Conda has prepared the above report.
```
This is from the **host shell**, not the container. Download output follows after. Not an error.

## Verified Commands

### Download (inside container)
```bash
export MODELSCOPE_ENDPOINT=https://www.modelscope.ai
/opt/conda/envs/sw2_public/bin/modelscope download \
  --model deepseek-ai/DeepSeek-V4-Flash-0731 \
  --local_dir /home/public/models/deepseekv4-flash-0731/ \
  --max-workers 8
```

### Check progress
```bash
# Disk size + shard count
docker exec jianliu_sw2_public_19255 bash -c \
  'du -sh /home/public/models/deepseekv4-flash-0731/; \
   ls /home/public/models/deepseekv4-flash-0731/*.safetensors 2>/dev/null | wc -l'

# Active process count
docker exec jianliu_sw2_public_19255 bash -c \
  'ps aux | grep modelscope | grep -v grep | wc -l'
```

### Kill all modelscope processes before restart
```bash
docker exec jianliu_sw2_public_19255 bash -c \
  'kill $(ps aux | grep "modelscope download" | grep -v grep | awk "{print \$2}") 2>/dev/null; sleep 2'
```

## Progress Log

| Time | Size | Shards | Process | Notes |
|------|------|--------|---------|-------|
| ~early | 88GB | 46/48 | running | SSH dropped, resumed |
| ~mid | 100GB | 46/48 | 2 processes | Old processes competing, killed |
| ~mid | 103GB | 46/48 | 1 process | Cleaned up |
| ~mid | 108GB | 46/48 | 1 process | model-00006 @92%, model-00009 @90% |
| ~late | 111GB | 46/48 | 1 process | Multiple shards downloading |
| ~3h | 140GB | 46/48 | 0 proc | Process exited, 2 shards stuck (00011, 00019) |
| ~4h | 140GB | 46/48 | 1 proc | Old stuck process found (no disk growth) |
| ~4.5h | 141GB | 46/48 | 2 proc | New download + old stuck process |
| ~5h | 143GB | 47/48 | 1 proc | model-00019 done; old process killed |
| ~5.5h | 143GB | 47/48 | 1 proc | **Only model-00011 remains** |

## Observed Speeds
- Fast: 1.5-43 MB/s (when server less loaded)
- Slow: 100-400 kB/s (server under heavy load)
- Speed varies significantly based on server I/O load

## Final Status (session end)
- **47/48 shards** downloaded; only `model-00011-of-00048.safetensors` missing (~3GB)
- `model-00019` completed after killing the stuck competing process
- **Root cause of stuck/missing shards:** modelscope uses `.incomplete` lock files for shards in-progress. Two competing processes each hold locks on overlapping shards, silently skipping each other's locked shards even when disk is growing. The new process sees `.incomplete` locks as "in progress" and skips those shards entirely.
- Kill ALL old processes before restarting download — process count alone is not sufficient (a stuck process looks identical to a running one in `ps`)
- Total expected: ~158GB, 48 safetensors
- Download auto-resumes on re-run, skipping already-completed shards