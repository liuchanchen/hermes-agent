#!/bin/bash
#=============================================================================
# GLM-5.1-NVFP4 Benchmark — 2048 in / 512 out / prefix cache sweep
# Concurrency=64, cache hit rate 0% / 40% / 80%
#
# Run on WSL: bash /home/jianliu/work/vllm-bench/bench_glm5_nvfp4_prefix_cache.sh
#
# Key flags for vllm bench serve:
#   --backend openai          → /v1/completions (clean output, no reasoning)
#   --backend openai-chat     → /v1/chat/completions (requires chat endpoint,
#                               causes content=null with --reasoning-parser glm45)
#   --random-prefix-len N    → N fixed prefix tokens for cache hits
#     0% cache  → --random-prefix-len 0
#     40% cache → --random-prefix-len 819 (819/2048 ≈ 40%)
#     80% cache → --random-prefix-len 1638 (1638/2048 ≈ 80%)
#   --max-concurrency 64      → 64 concurrent in-flight requests
#   --tokenizer /data/models/glm_5_1_nvfp4/  → local tokenizer (no HF download)
#   --tokenizer-mode slow     → avoid auto-detect hangs
#   HF_HUB_OFFLINE=1          → block any HuggingFace network calls
#
# Server access: bench runs via SSH to 70.96, venv at /data/venvs/vllm-ds4/
#=============================================================================
set -euo pipefail

API_KEY="${API_KEY:-sk-warpdriveai}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
MODEL="${MODEL:-glm5_1_fp8}"
RESULT_DIR="${RESULT_DIR:-/tmp/vllm_bench_results}"
INPUT_LEN=2048
OUTPUT_LEN=512
NUM_PROMPTS="${NUM_PROMPTS:-500}"
WARMUPS="${WARMUPS:-1}"
RATE="${RATE:-inf}"
CONCURRENCY="${CONCURRENCY:-64}"
RANDOM_RANGE="${RANDOM_RANGE:-0.1}"

REMOTE_HOST="${REMOTE_HOST:-10.10.70.96}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

mkdir -p "$RESULT_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
VLLM_BENCH="vllm bench serve"

run_bench() {
    local label="$1"
    local prefix_len="$2"
    local cache_pct="$3"
    shift 3

    local result_file="${RESULT_DIR}/${label}_${TIMESTAMP}.json"

    echo ""
    echo "======================================================================"
    echo "  Benchmark: $label  (cache ≈ ${cache_pct})"
    echo "  Input: ${INPUT_LEN} | Output: ${OUTPUT_LEN} | prefix_len: ${prefix_len} | concurrency: ${CONCURRENCY}"
    echo "  Started:   $(date)"
    echo "======================================================================"

    local cmd
    cmd="source ~/.bashrc && \\
export HF_HUB_OFFLINE=1 && \\
source /data/venvs/vllm-ds4/bin/activate && \\
$VLLM_BENCH \\
        --backend openai \\
        --base-url '$BASE_URL' \\
        --model '$MODEL' \\
        --tokenizer /data/models/glm_5_1_nvfp4/ \\
        --tokenizer-mode slow \\
        --endpoint /v1/completions \\
        --seed 42 \\
        --num-prompts '$NUM_PROMPTS' \\
        --num-warmups '$WARMUPS' \\
        --random-input-len '$INPUT_LEN' \\
        --random-output-len '$OUTPUT_LEN' \\
        --random-prefix-len '$prefix_len' \\
        --random-range-ratio '$RANDOM_RANGE' \\
        --max-concurrency '$CONCURRENCY' \\
        --save-result \\
        --result-dir '$RESULT_DIR' \\
        --result-filename 'glm5n_2048in_512out_${cache_pct}_${TIMESTAMP}.json' \\
        --save-detailed \\
        --disable-tqdm \\
        --disable-shuffle \\
        $@"

    ssh $SSH_OPTS jianliu@$REMOTE_HOST "$cmd" 2>&1 | tee -a "${RESULT_DIR}/${label}_${TIMESTAMP}.log"

    echo "  Done:      $(date)"
    echo "  Result:    ${result_file}"
    echo ""
}

# 0% cache hit
run_bench "glm5n_2048in_512out_0pct_cache" \
    0 "0%" \
    --request-rate "$RATE"

# 40% cache hit (819/2048 ≈ 40%)
run_bench "glm5n_2048in_512out_40pct_cache" \
    819 "40%" \
    --request-rate "$RATE"

# 80% cache hit (1638/2048 ≈ 80%)
run_bench "glm5n_2048in_512out_80pct_cache" \
    1638 "80%" \
    --request-rate "$RATE"

echo ""
echo "============================================================"
echo "  All benchmarks complete!"
echo "  Results: $RESULT_DIR/"
echo "  Timestamp: $TIMESTAMP"
echo "============================================================"