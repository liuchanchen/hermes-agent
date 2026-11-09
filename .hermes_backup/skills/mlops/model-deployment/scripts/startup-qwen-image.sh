#!/bin/bash
# Qwen-Image-2512 FastAPI diffusion server launcher for 10.10.70.88
# Usage: bash scripts/startup-qwen-image.sh

set -e
HOST="jianliu@10.10.70.88"
VENV="/data/venvs/vllm-ds4/bin/python3"
SERVER_SCRIPT="/data/scripts/qwen_image_server.py"
LOG="/tmp/qwen_image_server.log"
PORT=8000

echo "[$(date)] Starting Qwen-Image-2512 server..."

# Check if already running
if ssh "$HOST" "pgrep -f qwen_image_server | grep -v grep" 2>/dev/null | grep -q .; then
    echo "Already running. Killing old instance..."
    ssh "$HOST" "pkill -f qwen_image_server" 2>/dev/null || true
    sleep 2
fi

# Transfer server script (if locally modified — server script lives at /data/scripts/, not /tmp/)
# B64=$(base64 -w0 /tmp/qwen_image_server.py)
# ssh "$HOST" "mkdir -p /data/scripts && echo '$B64' | base64 -d > /data/scripts/qwen_image_server.py"

# Start
ssh "$HOST" "source ~/.bashrc && setsid $VENV $SERVER_SCRIPT </dev/null >$LOG 2>&1 &" &
SSH_PID=$!

echo "[$(date)] Server starting (setsid PID on remote). Log: $LOG"
echo "[$(date)] Check with: ssh $HOST 'tail -f $LOG'"
echo "[$(date)] Health: curl http://localhost:$PORT/"
echo "[$(date)] Benchmark: python3 scripts/qwen_benchmark.py"