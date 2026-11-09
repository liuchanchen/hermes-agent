---
name: remote-codex-management
description: Operate Codex CLI on remote servers via SSH.
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Codex, Remote, SSH, OpenAI, GPU-Server]
---

# Remote Codex Management

Runs and manages the OpenAI Codex CLI on remote GPU servers reached via SSH: locating the binary, fixing proxy connectivity, running jobs with a chosen model, upgrading, and checking the ChatGPT account's weekly rate limit. It does NOT cover how to write prompts for Codex or delegate coding work — see the `external-coding-agents` skill for that. All commands below execute on the remote host through the `terminal` tool (ssh); local read tools cannot see the remote filesystem.

## When to Use

- User asks to run a Codex job on a remote server (68.96, 68.88, etc.).
- `codex: command not found` on a server that previously used Codex.
- Codex fails to reach `api.openai.com` / times out refreshing models.
- User wants Codex to use a specific model (e.g. `gpt-5.6-sol`).
- User wants to upgrade the remote Codex CLI.
- User asks "what's my Codex weekly limit / account usage".

## Prerequisites

- SSH access to the remote host (key auth) from the machine running Hermes.
- Codex installed on the remote host. It may live under nvm, NOT on the default PATH: check `/home/<user>/.nvm/versions/node/*/bin/codex`.
- Node/npm available on the remote host (nvm's node provides npm).
- Codex logged in: `~/.codex/auth.json` present with `auth_mode: chatgpt` and a `tokens.access_token` (non-empty).
- A working HTTP/HTTPS proxy on the remote host to reach `api.openai.com` and `chatgpt.com` (the internal OpenAI API is not directly reachable from these servers).

## How to Run

Invoke every command through the `terminal` tool with `ssh -o StrictHostKeyChecking=no <host> '...'`. For Codex jobs, always export the proxy vars and the nvm bin dir first:

```bash
ssh <host> 'cd /home/<user>/work/<repo> && \
  export PATH=/home/<user>/.nvm/versions/node/<ver>/bin:$PATH && \
  export http_proxy=http://<proxy>:<port> https_proxy=http://<proxy>:<port> \
         HTTP_PROXY=http://<proxy>:<port> HTTPS_PROXY=http://<proxy>:<port> && \
  codex exec --model gpt-5.6-sol "task description"'
```

## Quick Reference

- Locate binary: `ls /home/<user>/.nvm/versions/node/*/bin/codex`
- Version: `codex --version`
- Login status: `codex login status`
- Run one-shot (needs git repo or flag): `codex exec --model <m> "<prompt>"`
- Run outside a git repo: `codex exec --model <m> --skip-git-repo-check "<prompt>"`
- Read-only sandbox: add `--sandbox read-only`
- List available models (verified 2026-10-15 on oemp106 via `~/.codex/models_cache.json`): `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-reserve`, `gpt-5.6-sol`, `gpt-5.6-terra`, … — **`gpt-5.4-mini`/`gpt-5.4` are REJECTED on ChatGPT accounts (400 invalid_request_error)**
- Config: `~/.codex/config.toml` (e.g. `model = "gpt-5.6-sol"`, `model_reasoning_effort = "xhigh"`)
- Auth: `~/.codex/auth.json` -> `tokens.access_token`
- Upgrade: `npm install -g @openai/codex@latest`
- Weekly limit API: `GET https://chatgpt.com/backend-api/codex/usage` with `Authorization: Bearer <access_token>`
- Account check: `GET https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27`

## Verified host: oemp106 (10.10.68.106)

- Binary: `/home/liujian/.nvm/versions/node/v24.17.0/bin/codex`; auth OK (ChatGPT account)
- Proxy: `.bashrc` exports `http://10.10.59.100:7890` (scheme present, link verified 2026-10-15)
- End-to-end smoke (2026-10-15): `codex exec --model gpt-5.6-sol --skip-git-repo-check --sandbox read-only` reached OpenAI and executed — gated only by the account's usage limit (reset 5:32 AM). Chain proven: ssh → nvm PATH → proxy → auth → model.
- In the DSH `oemp106` profile instance (port 3082), bash already executes ON oemp106 — call codex directly there (still export PATH+proxy).

## Procedure

### 1. Locate and sanity-check Codex
```bash
ssh <host> 'which codex; ls /home/<user>/.nvm/versions/node/*/bin/codex 2>/dev/null; codex --version 2>/dev/null || /home/<user>/.nvm/versions/node/*/bin/codex --version'
```
If `codex: command not found`, it is installed under nvm and simply not on the non-interactive SSH PATH — use the absolute path (remember: `bash -lc` does NOT load `.bashrc`, so proxy vars are absent too).

### 2. Verify proxy connectivity (the #1 failure mode)
```bash
ssh <host> 'grep -iE "^export (http|https)_proxy" ~/.bashrc'
```
**Pitfall**: a bare `10.10.60.140:7890` (no scheme) breaks everything. It must be `http://10.10.60.140:7890`. Test the link:
```bash
ssh <host> 'export https_proxy=http://<proxy>:<port>; timeout 15 curl -s -o /dev/null -w "%{http_code}\n" https://api.openai.com/v1/models'
```
`HTTP 401` = link works (401 is expected without a token). `TCP FAIL`/timeout = broken.

### 3. Fix the proxy lines in ~/.bashrc if the scheme is missing
Use a small python replace (sed quoting gets mangled over ssh); see `scripts/fix_proxy.py`. Backup first (`cp ~/.bashrc ~/.bashrc.bak.$(date +%s)`). Verify with `grep -nE "^export (http|https)_proxy" ~/.bashrc`.

### 4. Run a Codex job with a chosen model
```bash
ssh <host> 'cd /home/<user>/work/<repo> && \
  export PATH=/home/<user>/.nvm/versions/node/<ver>/bin:$PATH && \
  export http_proxy=http://<proxy>:<port> https_proxy=http://<proxy>:<port> \
         HTTP_PROXY=http://<proxy>:<port> HTTPS_PROXY=http://<proxy>:<port> && \
  timeout 100 codex exec --model gpt-5.4-mini --sandbox read-only "<prompt>"'
```
Use a short model (e.g. `gpt-5.4-mini`) for trivial smoke tests to save quota. Note `codex exec` reads prompt from stdin too; when run non-interactively it will say "Reading additional input from stdin..." — that is normal, not a hang.

### 5. Upgrade Codex
```bash
ssh <host> 'export PATH=/home/<user>/.nvm/versions/node/<ver>/bin:$PATH && \
  export http_proxy=http://<proxy>:<port> https_proxy=http://<proxy>:<port> && \
  npm install -g @openai/codex@latest'
```
Then verify `codex --version`.

### 6. Check the account weekly limit
Run `scripts/check_codex_limits.py` on the remote host (it reads `~/.codex/auth.json`, routes through the proxy, and calls the usage API):
```bash
scp scripts/check_codex_limits.py <host>:/tmp/ && ssh <host> 'python3 /tmp/check_codex_limits.py'
```
Key fields: `rate_limit.primary_window.used_percent` (used this week), `limit_window_seconds` (604800 = 7 days), `reset_after_seconds`, `plan_type`.

## Pitfalls

- **Non-interactive SSH does not load `.bashrc`** — proxy vars and nvm PATH are absent unless exported explicitly in the ssh command. `bash -lc` also does not reliably source it.
- **Proxy scheme missing** is the classic silent failure: `codex exec` starts, then dies with `failed to refresh available models: timeout waiting for child process to exit`. Fix = add `http://` prefix.
- **`codex models` needs a real TTY** and fails with "stdin is not a terminal" over plain ssh — read the model list from `~/.codex/models_cache.json` instead.
- **Codex refuses to run outside a git repo** — pass `--skip-git-repo-check` for ad-hoc jobs, or run from a repo directory.
- **`codex exec` can look hung** on first call (waiting on model refresh over a slow proxy). Wrap with `timeout 100` and be patient on cold starts.
- **Sed over ssh mangles single quotes** when fixing proxy lines — use a python replace or the provided script.
- **ChatGPT.com endpoints return 403/404 for most paths**; only `/backend-api/codex/usage` (and `accounts/check`) worked with a Bearer token. `api.openai.com/v1/me/*` returns 503 — don't use it.
- The ChatGPT Plus weekly Codex quota is per 7-day window; `used_percent` tells you how much is left before reset.
- **Model rotation**: skill-verified model names go stale (gpt-5.4 family rejected 2026-10-15 with 400 on ChatGPT accounts). When codex returns `invalid_request_error ... model is not supported`, read `~/.codex/models_cache.json` for current slugs instead of guessing.
- **Usage-limit ERROR still proves the chain works** — the request reached OpenAI and was gated by quota only; note the reset time from the message.

## Verification

Smoke test proves the whole chain (path + proxy + model + auth):
```bash
ssh <host> 'cd /home/<user>/work/<repo> && \
  export PATH=/home/<user>/.nvm/versions/node/<ver>/bin:$PATH && \
  export https_proxy=http://<proxy>:<port> http_proxy=http://<proxy>:<port> && \
  timeout 100 codex exec --model gpt-5.4-mini --skip-git-repo-check --sandbox read-only "Reply with exactly: codex works"'
```
Success = the reply text appears in the output followed by `tokens used`.
