# MTP Speculative Decoding Scaling Behavior

## Empirical Data: GLM-5.2-NVFP4 on 70.96 (8×RTX PRO 6000, 96 GB)

Tests with TP=8, DCP=4, decode-context-parallel-size=4, 512 out tokens.
Benchmark: `vllm bench serve --backend openai --dataset-name custom`.

### conc=16 (GPU NOT saturated)

| Config | Req/s | Out tok/s | Mean E2EL | vs Non-MTP |
|--------|-------|-----------|-----------|:----------:|
| Non-MTP | 10.11 | 5,174 | 1575ms | 1.00x |
| MTP2 k=1 | 9.76 | 4,997 | 1630ms | 0.97x |
| MTP2 k=2 | 9.87 | 5,053 | 1612ms | 0.98x |

Peak concurrent: 32, max-num-seqs=64 on server → GPU not fully utilized.
MTP overhead (draft forward + acceptance arbitration) outweighs the benefit.
All three configurations within ~3% of each other — effectively noise level.

### conc=32 (GPU saturated)

| Config | Req/s | Out tok/s | Mean E2EL | vs Non-MTP |
|--------|-------|-----------|-----------|:----------:|
| Non-MTP | 13.9 | 7,118 | 2295ms | 1.00x |
| MTP2 k=1 | 23.4 | 11,975 | 1324ms | 1.68x |

Peak concurrent: 63-64 → GPU near saturation.
MTP acceptance rate ~42.7% → each step produces ~0.85 extra tokens on average.
At high concurrency, the extra tokens per step deliver 1.68x throughput.

## The Scaling Rule

MTP benefit = f(concurrency, acceptance_rate, draft_overhead):

- **Low concurrency** (GPU not saturated): MTP overhead > benefit. Non-MTP is
  equal or slightly faster. The draft model's extra compute cannot be hidden
  in idle GPU cycles.
- **High concurrency** (GPU saturated): MTP overhead is amortized across more
  concurrent requests. The per-step token gain from speculative decoding
  translates directly into throughput improvement.

## Recommendation

1. **For MTP tuning:** benchmark at the target production concurrency level.
   Never extrapolate from low-concurrency tests.
2. **Compare k=1 and k=2** at the target concurrency — the optimal k depends on
   acceptance rate and whether the additional draft overhead pays for itself.
3. **Typical pattern:** k=1 is a safe default; k=2 may help if acceptance rate
   is high (>50%) and model is very large (overhead proportionally smaller).

## Raw Result Files

- Non-MTP: `decode_20260709_115746/glm5_2_nvfp4_512out_decode_conc_16_20260709_115746.json`
- MTP2 k=1 (conc=16): `decode_20260709_120240/glm5_2_nvfp4_512out_decode_conc_16_20260709_120240.json`
- MTP2 k=2 (conc=16): `decode_20260709_120742/glm5_2_nvfp4_512out_decode_conc_16_20260709_120742.json`
- MTP2 k=1 (conc=32): `decode_20260708_200911/glm5_2_nvfp4_512out_decode_conc_32_20260708_200911.json`
- Non-MTP (conc=32): `decode_20260708_200500/glm5_2_nvfp4_512out_decode_conc_32_20260708_200500.json`
