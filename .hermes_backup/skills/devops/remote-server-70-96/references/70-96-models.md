# 70.96 Model Storage

## Current models under /data/models/

| Directory | Model | Repo | Size |
|-----------|-------|------|------|
| `glm_5_1_nvfp4/` | NVIDIA GLM-5.1-NVFP4 | nvidia/GLM-5.1-NVFP4 | 434 GB (complete, 2026-06-03) |
| `glm_5_1_fp8/` | GLM-5.1-FP8 | THUDM/GLM-5.1-FP8 | ~704 GB (deployed) |
| `deepseekv4_pro/` | DeepSeek V4 Pro | deepseek-ai/DeepSeek-V4-Pro | (deployed) |
| `minimax_m2_7/` | MiniMax-M2-7B | minimax-lingual/MiniMax-M2-7B | (deployed) |
| `minimax_m2_7_nvfp4/` | MiniMax-M2-7B-NVFP4 | minimax-lingual/MiniMax-M2-7B-NVFP4 | (deployed) |

## Disk usage

- `/data` LVM: 3.5 TB total, ~2.0 TB used, ~1.4 TB free (as of 2026-06-03)

## GLM-5.1-NVFP4 Download Session (2026-06-03)

**Repo:** `nvidia/GLM-5.1-NVFP4` via `HF_ENDPOINT=https://hf-mirror.com`
**Total:** 59 files, 465.9 GB (49×10GB safetensors + config/tokenizer)
**CLI:** `/data/venvs/vllm-ds4/bin/hf` (hf-hub v1.17.0)
**Destination:** `/data/models/glm_5_1_nvfp4/`

### Key findings from this session

- **huggingface.co is blocked** from 70.96 (curl error 28/timeout). `hf-mirror.com` works.
- **`nohup ... &` kills the process** — the `hf download` process died silently multiple times when
  started with `nohup cmd &` in an SSH command. Process survived reliably when started with `setsid`.
  ```
  # WRONG (dies silently):
  ssh jianliu@10.10.70.96 "nohup env HF_ENDPOINT=... /data/venvs/vllm-ds4/bin/hf download ... &"
  # CORRECT (survives for hours):
  ssh jianliu@10.10.70.96 "setsid env HF_ENDPOINT=... /data/venvs/vllm-ds4/bin/hf download ... \
    </dev/null >/dev/null 2>&1"
  ```
- **`--max-workers 2`** — default 8 workers causes the downloader to die. 2 workers = stable.
- **Auto-resume works** — on restart, partial `.incomplete` files in `.cache/huggingface/download/`
  are reused, only missing bytes fetched. No `--resume-download` flag needed.
- **Download rate:** ~20 MB/s (~5–6 GB per 5 min). At this rate: 6–8 hours total.
- **Downloader PID (stable run):** 309547 (python3.12, ~22% CPU, survived >3.5 hours)

### Download progress log

| Time (CST) | Total MB | Shards done | Locks | Notes |
|-----------|----------|-------------|-------|-------|
| 10:40 | 0 | 0/49 | 8 | Started, small config files first |
| 10:53 | 15,799 | 0/49 | 8 | 1.2 GB/min initial rate |
| 11:15 | 40,789 | 7/49 | 8 | Process died (first run) |
| 11:16 | — | — | — | Restarted, resumed from partial files |
| 11:30 | 40,000 | 7/49 | 8 | Process died again |
| 11:31 | — | — | — | Restarted again |
| 12:15 | 81,000 | 8/49 | 7 | Process died again |
| 12:30 | — | — | — | Restarted with setsid — THIS run survived |
| 12:35 | 86,000 | 8/49 | 7 | |
| 13:00 | 104,000 | 10/49 | 7 | |
| 13:30 | 132,000 | 13/49 | 7 | |
| 14:00 | 160,000 | 16/49 | 7 | |
| 14:30 | 185,000 | 19/49 | 7 | |
| 15:00 | 197,000 | 21/49 | 7 | Session ended (iteration limit) |

**Final status at session end:** 21/49 shards completed, 197 GB downloaded, still running at PID 309547.
Est. remaining: ~270 GB → ~5–6 more hours.

### Second session (2026-06-03, completed)

Download was restarted after the first session ended. Initial 23 valid shards + 8 corrupt (model-00024-31)
were identified and deleted (corrupt = 1.5-1.7 GB HTML error pages from XetHub CAS without HF_TOKEN).
Final session (34→49 shards) ran from 20:10 to 21:32 CST, completing all 49 shards.

| Time (CST) | Shards | Size | Notes |
|-----------|--------|------|-------|
| 18:30 | 23/49 | 237G | Cleaned corrupt shards 24-31, restarted |
| 18:46 | 23/49 | 237G | Process died (CAS URL expiry) |
| 18:47 | 23/49 | — | Restarted, resumed |
| 19:00 | 25/49 | 244G | +2 new valid shards confirmed |
| 19:25 | 27/49 | 254G | +2 |
| 20:09 | 30/49 | 319G | Process died, restarted |
| 20:10 | 30/49 | 317G | Restarted (session 4) |
| 20:40 | 34/49 | 360G | +4 |
| 20:50 | 40/49 | 375G | +6 |
| 21:05 | 42/49 | 396G | +2 |
| 21:15 | 44/49 | 419G | +2 |
| 21:25 | 46/49 | 425G | +2 |
| 21:30 | 48/49 | 432G | +2 |
| 21:32 | **49/49** | **434G** | **COMPLETE** |

**Total:** 49 shards, 434 GB at `/data/models/glm_5_1_nvfp4/`
**Note:** Last 4 shards (46-49) are smaller (3.6-5 GB each) — normal for model tail (lm_head/embed layers).
Corrupt shards from initial run (24-31) were replaced with valid copies during final session.

### Monitor commands

```bash
# Quick status
ssh jianliu@10.10.70.96 "du -sh /data/models/glm_5_1_nvfp4/ && \
  find /data/models/glm_5_1_nvfp4 -maxdepth 1 -name 'model-*.safetensors' | wc -l && \
  find /data/models/glm_5_1_nvfp4/.cache -name '*.lock' | wc -l && \
  pgrep -fa 'hf download nvidia/GLM-5.1-NVFP4' | grep -v grep"

# If process died, restart with:
ssh jianliu@10.10.70.96 "source ~/.bashrc && setsid env HF_ENDPOINT=https://hf-mirror.com \
  /data/venvs/vllm-ds4/bin/hf download nvidia/GLM-5.1-NVFP4 \
  --local-dir /data/models/glm_5_1_nvfp4 --repo-type model --max-workers 2 \
  </dev/null >/dev/null 2>&1"
```

## Download history

See `references/downloads-log.md` under the `huggingface-mirror-download` skill for
per-session download records.