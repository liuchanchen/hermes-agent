#!/bin/bash
set -euo pipefail

MODEL_DIR=/data/models/glm_5_1_nvfp4/
LOG_FILE=/data/model_startup_script/glm5_nvfp4_docker.log
CONTAINER_NAME=glm5_nvfp4_vllm
IMG=voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412

echo "[$(date)] Starting GLM-5.1-NVFP4 vLLM (Docker) on 70.96" | tee -a "$LOG_FILE"

# --- 1. Kill stale processes and container ---
echo "[$(date)] Cleaning up stale processes..." | tee -a "$LOG_FILE"
pkill -9 -f 'vllm.*glm5_1_nvfp4' 2>/dev/null || true
sudo docker kill "$CONTAINER_NAME" 2>/dev/null || true
sleep 3

# --- 2. Clear Triton cache ---
rm -rf /root/.triton/cache 2>/dev/null || true
echo "[$(date)] Triton cache cleared" | tee -a "$LOG_FILE"

# --- 3. Start container in background (keep-alive) ---
echo "[$(date)] Starting Docker container..." | tee -a "$LOG_FILE"
sudo docker run -d \
  --rm \
  --gpus all \
  --ipc=host \
  --shm-size=16g \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --network host \
  --name "$CONTAINER_NAME" \
  --entrypoint /bin/bash \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v /data:/data \
  "$IMG" \
  -lc 'sleep infinity'

CONTAINER_ID=$(sudo docker ps -q -f name="$CONTAINER_NAME")
echo "[$(date)] Container started: $CONTAINER_ID" | tee -a "$LOG_FILE"
sleep 3

# --- 4. Write vLLM startup script inside container, then exec it ---
sudo docker exec "$CONTAINER_NAME" bash -c 'cat > /tmp/start_vllm.sh << '"'"'VLLM_EOF'"'"'
#!/bin/bash
export HF_HUB_OFFLINE=1
export VLLM_LOG_STATS_INTERVAL=1
export VLLM_ENABLE_PCIE_ALLREDUCE=1
unset VLLM_NVFP4_GEMM_BACKEND

cd /opt/vllm
exec python3 -m vllm.entrypoints.openai.api_server \
  --model /data/models/glm_5_1_nvfp4/ \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name glm5_1_fp8 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --decode-context-parallel-size 4 \
  --gpu-memory-utilization 0.82 \
  --max-num-seqs 64 \
  --kv-cache-dtype bfloat16 \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --tool-call-parser glm47 \
  --chat-template-content-format=string \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --moe-backend b12x
VLLM_EOF
chmod +x /tmp/start_vllm.sh
'

echo "[$(date)] Starting vLLM server via sudo docker exec..." | tee -a "$LOG_FILE"
sudo docker exec -d "$CONTAINER_NAME" bash /tmp/start_vllm.sh >> "$LOG_FILE" 2>&1

echo "[$(date)] vLLM server started in container $CONTAINER_ID" | tee -a "$LOG_FILE"
echo "[$(date)] Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "[$(date)] Waiting for server to come up (up to 180s)..." | tee -a "$LOG_FILE"

# --- 5. Poll /v1/models until ready ---
for i in $(seq 1 90); do
  if curl -s --connect-timeout 3 http://localhost:8000/v1/models 2>/dev/null | grep -q glm5_1_fp8 2>/dev/null; then
    echo "[$(date)] vLLM server is UP — model glm5_1_fp8 available" | tee -a "$LOG_FILE"
    exit 0
  fi
  sleep 2
done

echo "[$(date)] WARNING: /v1/models not responding after 180s — check log" | tee -a "$LOG_FILE"
tail -20 "$LOG_FILE" | tee -a "$LOG_FILE"
exit 1
