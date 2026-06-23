# TP8+EP + FP8 Block-k Alignment Failure

## Error

All 8 TP workers fail simultaneously during engine init:

```
ValueError: Weight input_size_per_partition = 64 is not divisible by weight quantization block_k = 128.
```

Seen on: Qwen3.6-35B-A3B-FP8 single-node with `--tensor-parallel-size 8 --enable-expert-parallel`.

## Root Cause

**EP shards experts across GPUs.** With EP=8 on single-node, each GPU holds 256/8 = 32 experts.

**TP shards weight matrices.** With TP=8, each GPU holds 1/8th of each expert's weight matrix.

Combined EP+TP, an expert's weight matrix `W` (hidden_dim=7168, intermediate_size=2048 for Qwen3.6 MoE) gets sharded:
- EP: `W → W_ep` where `W_ep` per GPU = 1/8th of the expert bank
- TP: `W_ep → W_tp` where each GPU holds 1/8th of `W_ep`

The resulting `input_size_per_partition` (hidden dim after EP+TP sharding) = 7168/8 = 896? No — for MoE experts with routing, the partition size is smaller. In Qwen3.6's case, `input_size_per_partition=64` after combined EP+TP sharding, which is the gating input dimension.

**FP8 quantization requires weights to be divisible into 128-element blocks.** A 64-element partition cannot be subdivided into 128-element FP8 blocks.

## Why DP=8 Works

DP=8 with TP=1 per rank: each rank has the full expert bank (EP shards experts across DP ranks, not within ranks). No TP sharding, so no `input_size_per_partition` mismatch. EP shards experts (256 total), each GPU holds 256/8=32 experts, but each expert is whole — no block_k problem.

## Config Matrix

| Config | EP | TP | FP8 Works? | Notes |
|--------|----|----|-----------|-------|
| TP8 + EP=8 (single-node) | yes | 8 | **NO** | block_k=128 conflict |
| TP8, no EP | no | 8 | YES | No expert sharding |
| DP=8, TP=1 (original qwen script) | yes | 1 | YES | EP shards across DP ranks |
| TP8 + EP=8 on BF16 model | yes | 8 | N/A | BF16 has no block_k |

## Workaround

For single-node FP8 MoE serving: use TP8 without EP, or DP=8 instead of TP8+EP.

```bash
# TP8, EP enabled (but EP weight filter disabled to avoid block_k)
vllm serve "$MODEL_PATH" \
  --tensor-parallel-size 8 \
  --enable-expert-parallel \
  # no --enable-ep-weight-filter  \
  --gpu-memory-utilization 0.92
```

For Qwen3.6-35B-A3B-FP8, the DP=8 script (`start_qwen36.sh`) is the correct working config.