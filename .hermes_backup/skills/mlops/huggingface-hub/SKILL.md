---
name: huggingface-hub
description: "HuggingFace hf CLI: search/download/upload models, datasets."
version: 1.0.0
author: Hugging Face
license: MIT
tags: [huggingface, hf, models, datasets, hub, mlops]
platforms: [linux, macos, windows]
---

# Hugging Face CLI (`hf`) Reference Guide

The `hf` command is the modern command-line interface for interacting with the Hugging Face Hub, providing tools to manage repositories, models, datasets, and Spaces.

> **IMPORTANT:** The `hf` command replaces the now deprecated `huggingface-cli` command.

## Quick Start
*   **Installation:** `curl -LsSf https://hf.co/cli/install.sh | bash -s`
*   **Help:** Use `hf --help` to view all available functions and real-world examples.
*   **Authentication:** Recommended via `HF_TOKEN` environment variable or the `--token` flag.

## Setup (always verify before use)

The skill does NOT guarantee `hf` is installed on remote servers. **Always check first:**

```bash
ssh <host> "/data/venvs/vllm-ds4/bin/hf --version"
# If not found → install via pip:
ssh <host> "/data/venvs/vllm-ds4/bin/pip install huggingface_hub -q"
```

> `pip install huggingface_hub` installs both the Python package AND the `hf` CLI wrapper.
> The deprecated `huggingface-cli` subcommand no longer works — use `hf` for all operations.
On proxy servers (70.95, 70.96), proxy is in `~/.bashrc` — `pip install` honors it.

**Chinese network: set `HF_ENDPOINT` before any HF operation:**
```bash
ssh <host> "echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc && source ~/.bashrc"
# Verify:
ssh <host> "hf env | grep ENDPOINT"
```
The huggingface.co CDN is blocked in mainland China. `hf-mirror.com` mirrors most files
and supports the same API. For CAS-backed files (e.g. `nvidia/` quantized models),
the signed redirect URL from hf-mirror.com reaches the CAS service directly.
On proxy servers (70.95, 70.96), proxy is in `~/.bashrc` — `pip install` honors it.

---
---

## Core Commands

### General Operations
*   `hf download REPO_ID`: Download files from the Hub. **No `--resume-download` flag** — the `hf` CLI v1.17.0 auto-resumes from cached files (checked via etag). For missing files, pass `--force-download` to override cache.
*   `hf upload REPO_ID`: Upload files/folders (recommended for single-commit).
*   `hf upload-large-folder REPO_ID LOCAL_PATH`: Recommended for resumable uploads of large directories.
*   `hf sync`: Sync files between a local directory and a bucket.
*   `hf env` / `hf version`: View environment and version details.

### Authentication (`hf auth`)
*   `login` / `logout`: Manage sessions using tokens from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
*   `list` / `switch`: Manage and toggle between multiple stored access tokens.
*   `whoami`: Identify the currently logged-in account.

**Auth check before downloading gated models** (e.g. `nvidia/GLM-5.1-NVFP4`):
```bash
ssh <host> "/data/venvs/vllm-ds4/bin/hf auth whoami"
# Error: Not logged in → model is gated, token required
```

**⚠️ XetHub CAS signed URL pitfall**: Many `nvidia/` and some other quantized models
store files on XetHub's CAS service (via `cas-bridge.xethub.hf.co`). The mirror redirect
gives a signed URL valid for ~1 hour. If the download stalls with HTTP 403 from CAS,
the signed URL has expired. **Refresh by re-fetching the redirect** from hf-mirror.com:

```bash
# Get fresh signed URL
curl -s -I "https://hf-mirror.com/nvidia/MODEL_NAME/resolve/main/shard-file.safetensors" \
  | grep -i location
```

> Even without HF_TOKEN, anonymous downloads can work if the CAS signed URL is fresh.
> The signed URL IS required — it's embedded in the hf-mirror redirect. Don't assume
> anonymous == no auth needed; XetHub CAS handles auth via the signed URL itself.
> If CAS returns 403, the signed URL is stale — refresh and retry.

**Gated models** from `nvidia/`, `meta/`, `mistralai/` etc. require:
1. Accepting the license at huggingface.co/model-card
2. A valid `HF_TOKEN` for API operations (repo info, file list)
3. For CAS-backed files, the signed redirect URL handles auth — token may not be needed
   for the actual download if the redirect is fresh.

## Python API (when `hf` CLI unavailable or for programmatic download)

On servers where the `hf` CLI is not installed or the `curl` install script times out,
use the Python `huggingface_hub` package directly. **Write script to file first, then run via SSH:**

```python
from huggingface_hub import snapshot_download
import os, sys

local_dir = "/data/models/glm_5_1_nvfp4"
repo_id = "nvidia/GLM-5.1-NVFP4"

existing = [f for f in os.listdir(local_dir) if f.endswith('.safetensors')]
print(f"Already have {len(existing)} shards")
sys.stdout.flush()

downloaded = snapshot_download(
    repo_id=repo_id,
    local_dir=local_dir,
    resume_download=True,
    allow_patterns=["*.safetensors", "*.json", "*.md", "*.jinja", "*.txt", "tokenizer*"],
    token=os.environ.get("HF_TOKEN"),   # None = anonymous, works for public repos
)
print(f"Download complete!")
```

> **Do NOT inline Python with `-c`** — the shell-escaping of quotes/braces causes bugs.
> Save to `/tmp/download_model.py` on the remote host, then run via `ssh host "nohup ... &"`.

Key parameter: `token` (huggingface_hub ≥ 1.0) accepts a string token or `None` (public models).
The old `hf_token` kwarg is **removed** — using it causes `TypeError: snapshot_download() got an unexpected keyword argument 'hf_token'`.

**Chinese network users: set `HF_ENDPOINT=https://hf-mirror.com`** in the environment
before any HF operation. The huggingface.co CDN is blocked in mainland China.

```python
# Before any HF API call:
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# OR pass endpoint directly:
snapshot_download(repo_id=..., endpoint="https://hf-mirror.com")
```
```

### Repository Management (`hf repos`)
*   `create` / `delete`: Create or permanently remove repositories.
*   `duplicate`: Clone a model, dataset, or Space to a new ID.
*   `move`: Transfer a repository between namespaces.
*   `branch` / `tag`: Manage Git-like references.
*   `delete-files`: Remove specific files using patterns.

---

## Specialized Hub Interactions

### Datasets & Models
*   **Datasets:** `hf datasets list`, `info`, and `parquet` (list parquet URLs).
*   **SQL Queries:** `hf datasets sql SQL` — Execute raw SQL via DuckDB against dataset parquet URLs.
*   **Models:** `hf models list` and `info`.
*   **Papers:** `hf papers list` — View daily papers.

### Discussions & Pull Requests (`hf discussions`)
*   Manage the lifecycle of Hub contributions: `list`, `create`, `info`, `comment`, `close`, `reopen`, and `rename`.
*   `diff`: View changes in a PR.
*   `merge`: Finalize pull requests.

### Infrastructure & Compute
*   **Endpoints:** Deploy and manage Inference Endpoints (`deploy`, `pause`, `resume`, `scale-to-zero`, `catalog`).
*   **Jobs:** Run compute tasks on HF infrastructure. Includes `hf jobs uv` for running Python scripts with inline dependencies and `stats` for resource monitoring.
*   **Spaces:** Manage interactive apps. Includes `dev-mode` and `hot-reload` for Python files without full restarts.

### Storage & Automation
*   **Buckets:** Full S3-like bucket management (`create`, `cp`, `mv`, `rm`, `sync`).
*   **Cache:** Manage local storage with `list`, `prune` (remove detached revisions), and `verify` (checksum checks).
*   **Webhooks:** Automate workflows by managing Hub webhooks (`create`, `watch`, `enable`/`disable`).
*   **Collections:** Organize Hub items into collections (`add-item`, `update`, `list`).

---

## Advanced Usage & Tips

### Global Flags
*   `--format json`: Produces machine-readable output for automation.
*   `-q` / `--quiet`: Limits output to IDs only.

### Extensions & Skills
*   **Extensions:** Extend CLI functionality via GitHub repositories using `hf extensions install REPO_ID`.
*   **Skills:** Manage AI assistant skills with `hf skills add`.
