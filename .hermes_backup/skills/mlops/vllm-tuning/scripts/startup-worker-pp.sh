#!/bin/bash
# PP=2 rank 1 (worker, headless), EP=8 — WORKS across 2 nodes with VLLM_HOST_IP + NCCL RoCE v2
# See references/pp-configuration.md for required env vars and setup.
# Phase 5.x - PP=2 rank 1 (worker), EP=8, batched-tokens=<B>, seqs=<N>
cd /data/venvs/vllm-ds4
source ~/.bashrc
source /data/venvs/vllm-ds4/bin/activate
rm -f /tmp/vllm_tp8_pp2.log
/usr/bin/nohup /data/venvs/vllm-ds4/bin/python3.12 /data/venvs/vllm-ds4/bin/vllm serve \
  /data/models/deepseekv4_pro --host 0.0.0.0 --port 8000 --trust-remote-code \
  --distributed-executor-backend mp \
  --tensor-parallel-size 8 --pipeline-parallel-size 2 \
  --nnodes 2 --node-rank 1 \
  --master-addr <MASTER_IP> --master-port 29505 \
  --enable-expert-parallel --kv-cache-dtype fp8 --block-size 256 \
  --max-model-len 1048576 --gpu-memory-utilization 0.93 \
  --max-num-seqs <N> --max-num-batched-tokens <B> \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE",\
    "compile_ranges_endpoints":[8192,16384,<B>]}' \
  --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice --reasoning-parser deepseek_v4 \
  --served-model-name deepseek_v4_pro \
  > /tmp/vllm_tp8_pp2.log 2>&1 &
echo "PID:$!"
