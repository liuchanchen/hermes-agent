# Qwen3.6-35B-A3B Serving — 2026-06-11

## Model locations

- Original FP16: `/data/models/Qwen3.6-35B-A3B`
- FP8 quantized: `/data/models/Qwen3.6-35B-A3B-FP8` ← used for serving

## Startup script

`/data/venvs/vllm-ds4/start_vllm_qwen.sh` — copied to `~/work/bench_test/qwen_3_6/start_qwen36.sh`

Key flags:
- `--enable-expert-parallel` (EP enabled)
- `--data-parallel-size 8` (DP=8, NOT TP8+EP)
- `--tool-call-parser qwen3_coder`
- `--reasoning-parser qwen3`
- `--language-model-only`
- `--gpu-memory-utilization 0.95`

## Current mode: DP=8 (not TP8+EP)

The script uses `--data-parallel-size 8` (DP=8) — vLLM spawns 8 separate model instances, each with TP=1. This is not the same as TP8+EP single-node.

**To create a TP8+EP single-node variant**, replace DP flags:
```bash
--tensor-parallel-size 8 \
--enable-expert-parallel \
--enable-ep-weight-filter \
--data-parallel-size 1 \   # or remove --data-parallel-size entirely
```

And set `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7` explicitly.

## Startup issues

- `FLASHINFER_DISABLE_VERSION_CHECK=1` needed (same flashinfer version mismatch as DeepSeek V4 Flash).
  Added to `start_qwen36.sh` on 2026-06-11.

## Server status (2026-06-11)

Running at `http://10.10.70.88:8000` — verified responding. `max_model_len: 262144` (256K context).

## Benchmark

Script: `test_qwen_throughput_cache.py` from `~/work/bandwidth_test/scripts/`
Benchmark dir: `/home/jianliu/work/bench_test/qwen_3_6/` (created 2026-06-11)