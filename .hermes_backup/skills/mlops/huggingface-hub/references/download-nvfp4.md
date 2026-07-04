# nvidia/GLM-5.1-NVFP4 Download Reference (2026-06-03)

## Model info
- **Repo**: `nvidia/GLM-5.1-NVFP4`
- **Files**: 59 total (49 safetensors shards + config/tokenizer/etc.)
- **Each shard**: ~545 MB → ~9.4 GB each (full model ~235 GB)
- **Storage**: XetHub CAS (`cas-bridge.xethub.hf.co`) — not vanilla HF CDN

## Error logs

### 1. `hf_token` wrong kwarg
```
TypeError: snapshot_download() got an unexpected keyword argument 'hf_token'
```
Fix: use `token=os.environ.get("HF_TOKEN")` in huggingface_hub ≥ 1.0

### 2. `Illegal header value b'Bearer '` (empty token)
```
httpcore.LocalProtocolError: Illegal header value b'Bearer '
httpx.LocalProtocolError: Illegal header value b'Bearer '
```
Cause: passed empty string `""` as token. Fix: pass `token=None` for anonymous/public models.

### 3. CAS 403 (signed URL expired)
```
curl: (22) The requested URL returned error: 403
```
The XetHub CAS signed URL embedded in hf-mirror redirect has a ~1 hour TTL.
When it expires, CAS returns 403. **Fix: re-fetch the redirect from hf-mirror.com
to get a fresh signed URL.**

### 4. `hf` CLI `No such option '--resume-download'`
```
Error: No such option '--resume-download'.
Available options for 'hf download': ...
  --force-download / --no-force-download
```
`hf` CLI v1.17.0 auto-resumes from cached files. No manual `--resume-download` flag.
Use Python API `snapshot_download(resume_download=True)` for explicit resume control.

## Successful download method

### Python API (works for public repos without token)
```python
from huggingface_hub import snapshot_download
import os, sys

downloaded = snapshot_download(
    repo_id="nvidia/GLM-5.1-NVFP4",
    local_dir="/data/models/glm_5_1_nvfp4",
    resume_download=True,
    allow_patterns=["*.safetensors", "*.json", "*.md", "*.jinja", "*.txt", "tokenizer*"],
    token=None,
    endpoint="https://hf-mirror.com",
)
```

### curl (for debugging / single files)
```bash
# Get fresh signed URL first
SIGNED_URL=$(curl -s -I "https://hf-mirror.com/nvidia/GLM-5.1-NVFP4/resolve/main/model-00024-of-00049.safetensors" \
  | grep -i location | awk '{print $2}' | tr -d '\r')

# Download with resume
curl -s --max-time 600 -L -C - \
  -o "/data/models/glm_5_1_nvfp4/model-00024-of-00049.safetensors" \
  "$SIGNED_URL"
```

## Verified connectivity from 10.10.70.96
- `https://hf-mirror.com` → HTTP 200 ✅
- `https://huggingface.co` (port 443) → **Connection timed out** ❌
- `https://cas-bridge.xethub.hf.co` → HTTP 403 (expired signed URL)
- hf-mirror API (`/api/models/nvidia/GLM-5.1-NVFP4`) → public model, no auth needed ✅

## Key lesson
XetHub CAS authentication is via **signed redirect URL**, not HF_TOKEN directly.
The hf-mirror.com redirect embeds the signed URL. When CAS returns 403, the signed
URL has expired — refresh by re-requesting the redirect from hf-mirror.com.