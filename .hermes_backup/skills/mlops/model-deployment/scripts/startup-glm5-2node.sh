#!/bin/bash
# GLM-5.1-FP8 2-node startup (master + worker)
set -euo pipefail
MODEL_PATH="/data/models/glm_5_1_fp8"
LOG_FILE="/tmp/vllm_glm5_$1.log"
HEAD_IP="192.168.66.10"
MASTER_PORT="${MASTER_PORT:-29505}"
export VLLM_ENGINE_READY_TIMEOUT_S=3600 VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=0
export NCCL_SOCKET_IFNAME=bond0 GLOO_SOCKET_IFNAME=bond0 TP_SOCKET_IFNAME=bond0
if [ "$1" = "master" ]; then export VLLM_HOST_IP="192.168.66.10"; else export VLLM_HOST_IP="192.168.66.20"; fi
export MASTER_ADDR="${HEAD_IP}"
export NCCL_IB_DISABLE=0 NCCL_IB_HCA=mlx5_bond_0 NCCL_DEBUG=WARN NCCL_IB_GID_INDEX=3
export NCCL_IB_TIMEOUT=23 NCCL_IB_QPS_PER_CONNECTION=4 NCCL_IB_TC=136
export NCCL_CROSS_NIC=0 NCCL_ALGO=Ring NCCL_MIN_NCHANNELS=8 NCCL_NET=IB
ulimit -n 1048576 2>/dev/null || ulimit -n 65535
export TRITON_MAX_SHARED_MEMORY=101376
source ~/.bashrc && source /data/venvs/vllm-ds4/bin/activate
echo "[$(date '+%H:%M:%S')] bond0: $(ip addr show bond0 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)"

COMMON_OPTS=(
  --host 0.0.0.0 --port 8000 --trust-remote-code
  --distributed-executor-backend mp
  --tensor-parallel-size 8 --pipeline-parallel-size 2 --nnodes 2
  --enable-expert-parallel
  --attention-backend TRITON_MLA
  --block-size 64 --max-model-len 65536 --gpu-memory-utilization 0.88
  --max-num-seqs 256 --max-num-batched-tokens 8192
  --enforce-eager --tokenizer-mode hf
  --hf-overrides '{"index_topk": 0}'
  --served-model-name glm5_1_fp8
  --chat-template-content-format=string
  --tool-call-parser glm47
  --enable-auto-tool-choice
  --reasoning-parser glm45
)

if [ "$1" = "master" ]; then echo "$(date) === MASTER ==="
  vllm serve "${MODEL_PATH}" "${COMMON_OPTS[@]}" --node-rank 0 --master-addr "${HEAD_IP}" --master-port "${MASTER_PORT}" 2>&1 | tee -a "$LOG_FILE"
else echo "$(date) === WORKER ==="
  vllm serve "${MODEL_PATH}" "${COMMON_OPTS[@]}" --node-rank 1 --master-addr "${HEAD_IP}" --master-port "${MASTER_PORT}" --headless 2>&1 | tee -a "$LOG_FILE"
fi
