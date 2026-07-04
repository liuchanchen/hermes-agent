#!/bin/bash
# Run the full S1+S2+S3 benchmark suite with a single label
# Usage: bash bench-all.sh <label>
# Example: bash bench-all.sh baseline_16384_256

set -euo pipefail
LABEL=${1:-unnamed}
DIR=/tmp/vllm_bench
mkdir -p "$DIR"

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ARGS="--backend openai-chat --endpoint /v1/chat/completions --tokenizer /data/models/deepseekv4_pro --model deepseek_v4_pro --request-rate inf --save-result --result-dir $DIR --disable-tqdm --temperature 0"

echo "=== S1: Short prompt (128/128, 10 concurrency) ==="
vllm bench serve $ARGS --dataset-name random --random-input-len 128 --random-output-len 128 --num-prompts 10 --result-filename "S1_${LABEL}.json"

echo "=== S2: Long prompt (60K/128, 5 concurrency) ==="
vllm bench serve $ARGS --dataset-name random --random-input-len 60000 --random-output-len 128 --num-prompts 5 --result-filename "S2_${LABEL}.json"

echo "=== S3: Prefix cache (60K prefix, 5 requests) ==="
vllm bench serve $ARGS --dataset-name prefix_repetition --prefix-repetition-prefix-len 60000 --prefix-repetition-suffix-len 128 --prefix-repetition-num-prefixes 1 --num-prompts 5 --result-filename "S3_${LABEL}.json"

echo "=== Summary ==="
for s in S1 S2 S3; do
  f="$DIR/${s}_${LABEL}.json"
  if [ -f "$f" ]; then
    python3 -c "import json; d=json.load(open('$f')); print(f'$s: completed={d[\"completed\"]}, failed={d[\"failed\"]}, TTFT={d[\"mean_ttft_ms\"]:.0f}ms, TPOT={d[\"mean_tpot_ms\"]:.1f}ms, throughput={d[\"output_throughput\"]:.1f}tok/s')"
  else
    echo "$s: NO RESULT"
  fi
done
