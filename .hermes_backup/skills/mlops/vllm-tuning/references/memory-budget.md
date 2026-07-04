# GPU Memory Budget — DeepSeek V4 Pro on 96GB Blackwell

## Measured Model Loading Cost (TP=8, EP=16, FP8)

| Configuration | Per-GPU Memory Used | Free Memory |
|--------------|-------------------|-------------|
| mode=3, custom_ops=["all"] | ~93.5 GiB | ~4.98 GiB |
| mode=3 (no custom_ops) | ~93.5 GiB | ~4.98 GiB |
| mode=0 (pure CUDA graphs) | ~93.5 GiB | ~4.98 GiB |
| After removing `custom_ops` | ~93.5 GiB | ~4.98 GiB |

## KV Cache Budget

| Configuration | Available for KV | Estimated max-model-len |
|--------------|-----------------|------------------------|
| DP=2 + custom_ops=["all"] + mode=3 | ~1.01 GiB | ~1,764 tokens |
| DP=2 + batched-tokens=32768 + mode=3 | ~5.53 GiB | ~9,748 tokens |
| DP=2 + batched-tokens=16384 + mode=3 | ~11.44 GiB | ~411,904 tokens |
| DP=2 (needs 24 GiB for 1M ctx) | ❌ Insufficient | ❌ |

## Key Finding

For 1M context length with fp8 KV cache:
- KV cache needed: **~24.06 GiB** (across 8 GPUs via TP=8)
- Available on 70.98 (96GB): **11.44 GiB max** (after model load + compilation)
- **1M context is NOT achievable** on 96GB Blackwell cards with full model load

## Memory-Saving Techniques Tried

| Technique | Effect |
|-----------|--------|
| Reducing `max-num-seqs` from 512→256→128 | No effect on KV cache memory |
| Removing `custom_ops:["all"]` | Freed enough for ~11.44 GiB KV |
| Reducing `max-num-batched-tokens` from 32768→16384 | Freed additional ~6 GiB for KV |

## Per-Config OOM Results (Actual Measurements)

| Config | max-model-len | KV cache needed | Available | Result |
|--------|--------------|----------------|-----------|--------|
| 16384/256 | 1048576 | 24.06 GiB | 5.86 GiB | ❌ OOM |
| 16384/128 | 200000 | 18.12 GiB | 5.86 GiB | ❌ OOM |
| 8192/256 | 200000 | 18.12 GiB | 21.61 GiB | ✅ Worked |
| 8192/128 | 1048576 | 24.06 GiB | 5.52 GiB | ❌ OOM |
| 8192/512 | 200000 | 18.12 GiB | 21.61 GiB | ✅ Worked |
| 32768/256 | 32000 | 18.12 GiB | 5.86 GiB | ❌ OOM |
| 32768/256 | 200000 | 18.12 GiB | 5.86 GiB | ❌ OOM |

**Key insight**: The KV cache requirement is a function of max-model-len AND max-num-seqs AND batched-tokens. The formula is complex but empirically, max-model-len = 200000 with batched-tokens <= 16384 and max-num-seqs <= 512 works, while batched-tokens >= 32768 always fails due to larger pre-allocation of cache blocks.

The 21.61 GiB available KV cache (vs 5.86 GiB) on the 8192 batch configs suggests smaller batch sizes reduce the KV cache block reservation.

## Memory-Saving Techniques Not Tried

- `--enforce-eager` (no CUDA graphs at all)
- `--kv-cache-dtype fp8_bf16` (might reduce KV per token)
- Reducing `--max-model-len` to 65536 (may free enough for 32768 configs)
- PP=2 (each node loads half the model → ~47 GiB/card for weights)
- Reducing `--gpu-memory-utilization` to 0.85 (actually makes it WORSE)
