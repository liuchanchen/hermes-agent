# DeepSeek-V4 SM12x sparse MLA paged-attention kernels (jasl/vllm ds4-sm120)

Source of truth: `jasl/vllm` fork, branch `ds4-sm120`, file
`vllm/v1/attention/backends/mla/sparse_mla_kernels.py` (read 2026-08-06).
There is NO file named `sparse_mla_sm120_paged_attention.py` — the sm120
paged sparse-MLA kernels live in `sparse_mla_kernels.py` (2694 lines). The
name `sparse_mla_sm120_paged_attention` colloquially refers to this family.

## What it is

Triton paged sparse-MLA attention kernels for Blackwell (sm_120 / CC 12.0) —
the decode/accumulate path for DeepSeek-V4's compressed-sparse attention
(CSA). Given a sparse set of candidate KV entries (selected by the Lightning
Indexer), they gather them from a PAGED KV cache and run online-softmax
attention, keeping state in FP8 with block-wise quant scales.

## Why sm120 mattered

DeepSeek-V4 / GLM-5.x sparse-MLA backends historically had no Blackwell
(CC 12.0) support. GLM-5.1-FP8 forced `is_v32=True` (from `index_topk` in
model config), which forces the SPARSE path, and none of the sparse MLA
backends supported sm120 — the failure we hit on the 70.96/70.98 GLM deploy.
This fork branch adds the SM12x sparse kernels + FP8 einsum path
(`ops/deepseek_v4_ops/fp8_einsum.py`) + DeepGEMM metadata routing. To force
dense instead, inject `--hf-overrides '{"index_topk": 0, "force_dense_mla": true}'`.

## The three kernels (line refs into sparse_mla_kernels.py)

1. `accumulate_fp8ds_paged_sparse_mla_attention_chunk` (L1552) — per-chunk
   accumulation. Args: `q[T,H,512]`, `k_cache` uint8, `block_table`,
   `seq_lens`, `gather_lens`, `block_size`, running state `max_score`/
   `denom`/`acc` (fp32), `candidate_offset`/`num_candidates`.
2. `fp8ds_paged_sparse_mla_attention_with_sink_multihead` (L1971) — decode
   kernel with an **attention sink** (fights entropy collapse in long sparse
   context); adds `attn_sink`, `head_block_size` in {1,2,4}.
3. `fp8ds_global_paged_sparse_mla_attention_with_sink_multihead` (L2235) —
   global-context variant fusing TWO paged uint8 caches in one pass:
   - `compressed_k_cache` + `slot_ids` + `topk_lens` + `compressed_block_size`
     = the CSA sparse top-k compressed KV
   - `swa_k_cache` + its own `block_table` = the sliding-window branch
   Each has its own `num_*_candidates`.

## FP8 paged-cache token layout

From the kernel body:
```
token_data_size = 448 (FP8) + 64 (BF16 RoPE) + 8 (scale)   # per token
                  fp8_dim    rope_dim                       scale_dim (8)
quant_block_size = 64                                       # per dequant group
dequant_scale = exp2(encoded_scale - 127.0)
```
- Data dims: FP8 e4nv, dequantized per-64-element block with encoded scale.
- RoPE dims: BF16, loaded via separate pointer offset from the FP8 block.
- `dim_mask` selects FP8 vs RoPE dims (CSA "mixed precision").
- Online softmax per candidate: `next_max=max(running_max,score)`,
  rescale `running_acc`/`running_denom`, then accumulate.

## Related fork files (mla/ backend dir)

`aiter_triton_mla.py`, `cutlass_mla.py`, `flashattn_mla.py`,
`flashinfer_mla.py`, `flashinfer_mla_sparse.py`, `flashmla.py`,
`flashmla_sparse.py`, `indexer.py` (Lightning Indexer, 30687 B),
`sparse_mla_env.py`, `sparse_mla_kernels.py`, `sparse_mla_reference.py`,
`sparse_swa.py`, `sparse_utils.py`, `triton_mla.py`, `xpu_mla_sparse.py`.
