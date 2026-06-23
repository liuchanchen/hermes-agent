#!/bin/bash
#=============================================================================
# DeepSeek V4 Flash - Throughput Benchmark Wrapper
# Tests cache hit rate: 0%, 40%, 80%
# IMPORTANT: base-url must be http://localhost:8000 (no /v1/completions suffix)
# test_deepseekv4_throughput_cache.py appends /v1/chat/completions internally.
#=============================================================================

set -e

INPUT_TOKENS=${INPUT_TOKENS:-2048}
OUTPUT_TOKENS=${OUTPUT_TOKENS:-500}
CONCURRENCY=${CONCURRENCY:-64}
MODEL=${MODEL:-/home/jianliu/work/models/deepseekv4_flash}
BASE_URL=${BASE_URL:-http://localhost:8000}
RESULT_DIR=${RESULT_DIR:-/home/jianliu/work/bench_test/deepseekv4_flash/results}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULT_DIR"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
TEST_CODE="$SCRIPT_DIR/test_deepseekv4_throughput_cache.py"

for CACHE_RATE in 0.0 0.4 0.8; do
    LABEL=$(echo "${CACHE_RATE}" | tr '.' 'p')
    echo "=== Running: cache_hit_rate=${CACHE_RATE} ==="
    python "$TEST_CODE" \
        --base-url "$BASE_URL" \
        --model "$MODEL" \
        --requests 200 \
        --concurrency "$CONCURRENCY" \
        --input-tokens "$INPUT_TOKENS" \
        --output-tokens "$OUTPUT_TOKENS" \
        --cache-hit-rate "$CACHE_RATE" \
        --save-json "$RESULT_DIR/dsv4_flash_${INPUT_TOKENS}in_${OUTPUT_TOKENS}out_c${LABEL}_${TIMESTAMP}.json"
    echo "=== Done: cache_hit_rate=${CACHE_RATE} ==="
done

echo "All runs complete. Results in $RESULT_DIR/"