# ModelScope Download — 2026-08-05 Late Session Reference
## DeepSeek-V4-Flash-0731 Final Completion Attempt

### Key Findings

#### 1. model-00045 is a small tokenizer shard (~1GB vs ~3.4GB for safetensors)
- All other shards (00001-00048) are 3.4-3.5GB
- model-00045-of-00048.safetensors is only 0.99GB (a tokenizer or metadata file, NOT a weight shard)
- This causes repeated download stalls: modelscope completes it to ~40-68%, SSH drops, modelscope deletes the partial file on channel exit, download restarts, stalls again
- **The file itself is correct size (0.99GB)** — it is not corrupted, it is a different type of file
- **Fix for stuck model-00045:** `rm -v model-00045-of-00048.safetensors` then restart — it re-downloads from 0

#### 2. modelscope exit code 1 = tokenizer.json timeout (not SSH disconnect)
- Previous sessions: exit code 255 = SSH channel dropped (normal)
- This session: exit code **1** = modelscope hit `MaxRetryError` on `tokenizer.json` (6MB file) — `ReadTimeoutError("HTTPSConnectionPool(host='www.modelscope.cn', port=443): Read timed out.")`
- This happens AFTER all 48 safetensors complete — modelscope then tries to download the tokenizer/metadata files
- The tokenizer download is separate from the safetensor shards and can fail independently
- **Safetensor completion (47/48 or 48/48) still possible even with exit code 1**

#### 3. Small shard bulk deletion still works — even for the tiny model-00045
- After hitting 47/48 with model-00045 corrupted, `rm model-00045-of-00048.safetensors` forced immediate re-download from 0
- modelscope auto-resumes from the deletion event — no need to manually restart
- Pattern: when stuck at N-1 shards and the remaining shard is small (<2GB), just delete it and the running process (or restart) picks it up immediately

#### 4. Final state: 48/48 at 156GB
- Downloaded 47 complete safetensors (3.4-3.5GB each)
- Downloaded model-00045 (1GB tokenizer shard)
- Total: 156GB, 48 files
- Note: total ~156GB (not 158GB) because model-00045 is only 1GB

### Commands Used
```bash
# Delete the stuck small shard
rm -v model-00045-of-00048.safetensors

# Restart after deletion
ssh -o ConnectTimeout=120 jianliu@192.168.12.12 \
  "docker exec jianliu_sw2_public_19255 bash -c 'export MODELSCOPE_ENDPOINT=https://www.modelscope.ai && /opt/conda/envs/sw2_public/bin/modelscope download --model deepseek-ai/DeepSeek-V4-Flash-0731 --local_dir /home/public/models/deepseekv4-flash-0731/ --max-workers 8 2>&1'"

# Verify completion
du -sh /home/public/models/deepseekv4-flash-0731/
ls /home/public/models/deepseekv4-flash-0731/*.safetensors | wc -l
du -sh /home/public/models/deepseekv4-flash-0731/*.safetensors | sort -h
```

### Disk Size Progression (this session)
| Time | Size | Files | Notes |
|------|------|-------|-------|
| Start | 149GB | 30 | after deleting 9 corrupted shards |
| +10min | 150GB | 38 | model-00011 started |
| +15min | 151GB | 40 | |
| +20min | 152GB | 41 | |
| +30min | 153GB | 41 | |
| +40min | 154GB | 44 | |
| +50min | 155GB | 46 | |
| +60min | 156GB | 48 | **COMPLETE** |