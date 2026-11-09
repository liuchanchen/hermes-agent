---
name: agentx-aiperf-benchmark
description: Run AgentX benchmark via AIPerf (agentic LLM serving load).
version: 0.1.0
author: Hermes Agent
license: Proprietary
platforms: [linux]
metadata:
  hermes:
    tags: [AgentX, AIPerf, Benchmark, Agentic, LLM-Serving, SemiAnalysis]
---

# AgentX Benchmark via AIPerf

Run the SemiAnalysis InferenceX **AgentX MVP** benchmark (agentic coding-agent workload) with **AIPerf**. Replays real Claude Code session traces (Weka corpus) — long context, multi-turn, prefix/KV reuse, subagent DAG — against any OpenAI-compatible inference server.

## When to Use

- "Run AgentX benchmark / smoke test"
- Benchmark an LLM server with agentic/coding-agent workload (vs fixed ISL/OSL)
- Test Prefix Cache / KV-offload / session-affinity behavior under real agent traffic

## Prerequisites

- **AIPerf installed** in a **Python ≥3.11** venv (AIPerf 0.12.0 requires `<3.14,>=3.11`; Ubuntu 22.04 default 3.10 is TOO OLD).
- **HuggingFace access** for the Weka trace dataset (auto-downloaded). On CN-network servers use proxy (e.g. 68.88's `http://10.10.60.140:7890`) or `HF_ENDPOINT=https://hf-mirror.com`.
- OpenAI-compatible server reachable; `--api-key` if it needs auth.
- Tokenizer resolvable from `--model` (HF repo) OR pass `--tokenizer <local-path>` for a local server alias.

## Install AIPerf (fast path on CN network)

```bash
# Ubuntu 22.04: python3.11 needed (3.10 rejected)
sudo apt-get install -y python3.11 python3.11-venv   # cache sudo first: printf '%s\n' "$PW" | sudo -S -v
/usr/bin/python3.11 -m venv aiperf-env
# Use Aliyun mirror — pypi.org is slow/unreliable from CN:
/home/jianliu/aiperf-env/bin/pip install -U aiperf -i https://mirrors.aliyun.com/pypi/simple/
```

## Smoke Test Command (verified working 2026-08-26, deepseekv4-flash)

```bash
export PATH=/home/jianliu/aiperf-env/bin:$PATH
export http_proxy=http://10.10.60.140:7890   # if HF not reachable directly
export https_proxy=http://10.10.60.140:7890
export no_proxy=localhost,127.0.0.1,10.0.0.0/8
export AIPERF_DATASET_CONFIGURATION_TIMEOUT=1800   # big dataset needs this
export AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT=1800

aiperf profile \
    --scenario inferencex-agentx-mvp \
    --url http://192.168.12.12:19258/v1 \
    --model deepseekv4-flash \
    --api-key '__WD_DEEPSEEKV4_FLASH__' \
    --endpoint-type chat \
    --public-dataset semianalysis-cc-traces-weka-062126 \
    --num-dataset-entries 2 \
    --concurrency 2 \
    --benchmark-duration 900 \
    --random-seed 20260826 \
    --use-server-token-count \
    --tokenizer /modelzoo/deepseekv4-flash-0731 \
    --artifact-dir ./agentx-smoke-out
```

**Verified smoke result** (deepseekv4-flash, 51 req, 892s): `submission_valid: true`; TTFT P50 4.3s / P95 7.8s; ITL mean 15.4ms; Effective Total Throughput 5,297 tok/s; **Theoretical Prefix Cache Hit 95.91%**.

## Key Parameters

| Flag | Meaning |
|------|---------|
| `--scenario inferencex-agentx-mvp` | Locks AgentX replay rules (streaming, cache-bust, idle-cap 10s, trajectory 0-1) |
| `--concurrency N` | Active Agent session trees (NOT http requests; subagents raise in-flight) |
| `--benchmark-duration` | **Min 900s**, default 1800s; shorter is rejected |
| `--num-dataset-entries N` | Load only first N traces — **use for smoke tests** |
| `--public-dataset` | Use **hyphenated** names: `semianalysis-cc-traces-weka-062126` / `...-256-k` |
| `--random-seed` | Fix for reproducible A/B comparisons |
| `--use-server-token-count` | Use server-reported token counts (recommended) |
| `--max-context-length` | Coarse trace filter; prefer `_256k` corpus for 256k servers |

## Result Files (in --artifact-dir)

- `profile_export_aiperf.json` / `.csv` — **final metrics** (TTFT, ITL, throughputs, prefix-cache-hit, `submission_valid`)
- `profile_export.jsonl` — raw per-request records
- `logs/aiperf.log` — full run log

## Pitfalls

- **Python 3.10 rejected** — AIPerf 0.12.0 needs ≥3.11. Install python3.11 (apt on 22.04 has `3.11.0~rc1`).
- **pypi.org slow/times out from CN** — use `-i https://mirrors.aliyun.com/pypi/simple/`.
- **huggingface.co unreachable (Errno 101 Network unreachable)** on cluster servers — use proxy (68.88: `10.10.60.140:7890`, already in 107's bashrc) or `HF_ENDPOINT=https://hf-mirror.com`.
- **Dataset configure timeout** — large traces.jsonl (1.7GB cache) + AWS-CDN download exceeds default 5min. Set `AIPERF_DATASET_CONFIGURATION_TIMEOUT=1800` + `AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT=1800`.
- **Dataset name hyphenation** — `--public-dataset` uses `semianalysis-cc-traces-weka-...` (hyphens), NOT the underscore form in some docs.
- **Local model alias tokenizer** — pass `--tokenizer /modelzoo/<model-dir>` (has tokenizer.json); `--model` alias alone won't resolve on HF.
- **68.107 conda pollution** — login shell dumps a broken-conda error; wrap remote cmds in `bash --noprofile --norc -c '...'`.
- **vLLM prompt-cache metrics** — enable `--enable-prompt-tokens-details` server-side for cached-token stats; otherwise Prefix Cache Hit shows theoretical only.
