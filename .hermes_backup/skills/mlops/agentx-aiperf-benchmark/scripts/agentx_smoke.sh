#!/bin/bash
# AgentX smoke test — verified 2026-08-26 on deepseekv4-flash (192.168.12.12:19258)
# Adjust URL / MODEL / API_KEY / tokenizer for your target server.
set -e
export PATH=/home/jianliu/aiperf-env/bin:$PATH

# Proxy from 70.88 — needed if huggingface.co is not directly reachable
export http_proxy=http://10.10.60.140:7890
export https_proxy=http://10.10.60.140:7890
export no_proxy=localhost,127.0.0.1,10.0.0.0/8
export NO_PROXY=localhost,127.0.0.1,10.0.0.0/8

# Big Weka trace dataset needs longer configure timeout than the 5min default
export AIPERF_DATASET_CONFIGURATION_TIMEOUT=1800
export AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT=1800

API_KEY="__WD_DEEPSEEKV4_FLASH__"
BASE_URL="http://192.168.12.12:19258/v1"
MODEL="deepseekv4-flash"
TOKENIZER="/modelzoo/deepseekv4-flash-0731"   # local path with tokenizer.json

mkdir -p /home/jianliu/work/agentx-smoke
cd /home/jianliu/work/agentx-smoke

aiperf profile \
    --scenario inferencex-agentx-mvp \
    --url "$BASE_URL" \
    --model "$MODEL" \
    --api-key "$API_KEY" \
    --endpoint-type chat \
    --public-dataset semianalysis-cc-traces-weka-062126 \
    --num-dataset-entries 2 \
    --concurrency 2 \
    --benchmark-duration 900 \
    --random-seed 20260826 \
    --use-server-token-count \
    --tokenizer "$TOKENIZER" \
    --artifact-dir ./agentx-smoke-out

echo "=== AGENTX SMOKE DONE (exit $?) ==="
# Results: ./agentx-smoke-out/profile_export_aiperf.json / .csv
