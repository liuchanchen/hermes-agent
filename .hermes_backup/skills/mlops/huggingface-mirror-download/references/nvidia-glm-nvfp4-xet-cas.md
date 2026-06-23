# NVFP4 Download via hf-mirror.com — XetHub CAS (corrected 2026-06-03)

> **CORRECTED 2026-06-03:** The original analysis below was wrong. `nvidia/GLM-5.1-NVFP4`
> downloaded fully without any `HF_TOKEN`. CAS signed URLs worked anonymously throughout.
> hf-mirror.com's XetHub CAS integration does NOT always require auth.

## Original Discovery (partially revised)

Downloading `nvidia/GLM-5.1-NVFP4` via `HF_ENDPOINT=https://hf-mirror.com` initially stalled:
- Early shards succeeded, then later shards showed ~1.5-1.7 GB file sizes instead of ~9.3 GB
- The small files were HTML error pages from XetHub CAS redirects

**Root cause (REVISED):** The early HTML error pages were likely from XetHub CAS signed URL
expiry during the first run. With a fresh session (kill → clean cache → restart), the CAS
redirects returned valid model files. No token was needed.

## Final Result (2026-06-03)

- **49/49 shards, 434 GB** at `/data/models/glm_5_1_nvfp4/`
- No `HF_TOKEN` provided at any point
- 4 restarts required over ~6 hours due to CAS URL expiry (~2-3 hours per run)
- All shards verified: 00001-00045 at ~9.3 GB; 00046-00049 at 3.6-5 GB (lm_head/embed tail — normal)

## Verification Test (still useful for diagnosing auth issues)

```bash
ssh jianliu@10.10.70.96 "curl -sI 'https://hf-mirror.com/nvidia/GLM-5.1-NVFP4/resolve/main/model-00024-of-00049.safetensors'"
# HTTP/2 302 + tiny content-length (~1058 bytes) → XetHub CAS returned HTML error
# HTTP/2 200 + large content-length (~9GB) → anonymously downloadable
```

## Key Lesson

**Do not assume `HF_TOKEN` is mandatory for `nvidia/` namespace models.** Always try without token first.
Monitor new shard sizes: real shards ~9.3 GB for this model, HTML errors ~1.5-1.7 GB.
If small files appear, stop, delete small shards, clean cache, and either restart or provide `HF_TOKEN`.