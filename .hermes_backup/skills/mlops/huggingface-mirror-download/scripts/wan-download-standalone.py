#!/usr/bin/env python3
"""
Standalone HuggingFace model downloader with resume support.

Bypasses huggingface_hub's lock mechanism when hf download hangs on
slow connections. Uses direct 'requests' HTTP streaming instead.

Usage:
  1. Copy this script and set HF_BASE + FILES for your model
  2. python3 wan-download-standalone.py
  3. (Optional) chain with rsync to transfer to remote server

Per-file retry: up to 10 attempts with exponential backoff.
Workers: 3 parallel streams by default (configurable via MAX_WORKERS).

See SKILL.md > "Python requests-based downloader" for full context.
"""
import os
import sys
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ──────────────────────────────────────────────────────────────────
LOCAL_DIR = r'/mnt/c/Users/liuch/My Documents/warpdriveai/models/wan2.2_t2v_A14B'
HF_BASE  = 'https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B/resolve/main'
LOG_FILE = '/tmp/model_download.log'
MAX_WORKERS = 3
RETRY_DELAY = 5

# File list: replace with your model's file list
# Get it via: from huggingface_hub import HfApi; api=HfApi(); api.list_repo_files('org/model')
FILES = [
    # List of relative file paths from repo root, e.g.:
    # "README.md",
    # "model-00001-of-00009.safetensors",
    # "subdir/config.json",
]
# ── END CONFIG ──────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update({"User-Agent": "hf-downloader/1.0"})

def log(msg):
    """Write to both LOG_FILE and stdout, flushing immediately."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(line)
        f.flush()
    print(line, end="", flush=True)

def download_file(filepath):
    """Download a single file with resume support."""
    local_path = os.path.join(LOCAL_DIR, filepath)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    url = f"{HF_BASE}/{filepath}"

    if os.path.exists(local_path) and os.path.getsize(local_path) > 100:
        log(f"[SKIP] {filepath} already exists")
        return filepath, True

    temp_path = local_path + ".partial"
    resume_pos = 0
    if os.path.exists(temp_path):
        resume_pos = os.path.getsize(temp_path)
        log(f"[RESUME] {filepath} resuming from {resume_pos} bytes")

    for attempt in range(10):
        try:
            headers = {"Range": f"bytes={resume_pos}-"} if resume_pos > 0 else {}
            resp = session.get(url, stream=True, timeout=120, headers=headers)

            # HTTP 416 = range not satisfiable → file already fully downloaded
            if resp.status_code == 416:
                if os.path.exists(temp_path):
                    os.rename(temp_path, local_path)
                return filepath, True

            if resp.status_code not in (200, 206):
                log(f"[WARN] {filepath} HTTP {resp.status_code}, attempt {attempt+1}")
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue

            mode = "ab" if resume_pos > 0 else "wb"
            with open(temp_path, mode) as f:
                downloaded = resume_pos
                for chunk in resp.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        f.flush()
                        downloaded += len(chunk)

            # Guard: 0-byte partial after resume means the server sent nothing new
            final_size = os.path.getsize(temp_path)
            if final_size == resume_pos and resp.status_code == 206:
                log(f"[WARN] {filepath} no new data (still {final_size} bytes), retrying from 0")
                resume_pos = 0
                os.remove(temp_path)
                continue

            # Guard: file was written but ended up at 0 bytes (broken connection)
            if final_size == 0:
                log(f"[WARN] {filepath} downloaded 0 bytes, retrying...")
                os.remove(temp_path)
                continue

            os.rename(temp_path, local_path)
            size_mb = os.path.getsize(local_path) / 1024**2
            log(f"[DONE] {filepath} ({size_mb:.1f} MB)")
            return filepath, True

        except Exception as e:
            log(f"[ERROR] {filepath} attempt {attempt+1}: {e}")
            time.sleep(RETRY_DELAY * (attempt + 1))

    return filepath, False

def main():
    log("=== Starting model download ===")
    log(f"Target: {LOCAL_DIR}")
    log(f"Files: {len(FILES)}")
    log(f"Workers: {MAX_WORKERS}")

    skipped = [f for f in FILES if os.path.exists(os.path.join(LOCAL_DIR, f))
               and os.path.getsize(os.path.join(LOCAL_DIR, f)) > 100]
    remaining = [f for f in FILES if f not in skipped]
    log(f"Already have: {len(skipped)}/{len(FILES)}")
    log(f"Need to download: {len(remaining)}")

    completed, failed = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        fut_map = {executor.submit(download_file, f): f for f in remaining}
        for fut in as_completed(fut_map):
            f, ok = fut.result()
            (completed if ok else failed).append(f)

    total_mb = sum(os.path.getsize(os.path.join(LOCAL_DIR, f)) / 1024**2
                   for f in FILES if os.path.exists(os.path.join(LOCAL_DIR, f)))

    log(f"=== Summary ===")
    log(f"Completed: {len(completed)}, Skipped: {len(skipped)}, Failed: {len(failed)}")
    log(f"Total size: {total_mb:.1f} MB")
    if failed:
        log(f"FAILED: {failed}")
        sys.exit(1)
    log("All files downloaded successfully!")

if __name__ == "__main__":
    main()
