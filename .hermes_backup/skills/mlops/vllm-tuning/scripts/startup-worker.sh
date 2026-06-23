#!/bin/bash
# DP=2 rank 1 (worker, headless), TP=8, EP=16, batched-tokens=<B>, seqs=<N>
# NOTE: Do NOT add --api-server-count 1 here — it conflicts with --headless
# and causes the worker to crash immediately.
vllm serve /data/models/deepseekv4_pro \
  --host 0.0.0.0 --port 8000 --trust-remote-code \
  --distributed-executor-backend mp --headless \
  --tensor-parallel-size 8 --pipeline-parallel-size 1 \
  --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend mp \
  --data-parallel-address 10.10.71.96 \
  --nnodes 2 --node-rank 1 \
  --master-addr 10.10.71.96 --master-port 29505 --data-parallel-rpc-port 29550 \
  --enable-expert-parallel \
  --kv-cache-dtype fp8 --block-size 256 \
  --max-model-len 1048576 --gpu-memory-utilization 0.93 \
  --max-num-seqs 256 --max-num-batched-tokens 16384 \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE","compile_ranges_endpoints":[8192,16384]}' \
  --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice --reasoning-parser deepseek_v4 \
  --served-model-name deepseek_v4_pro
