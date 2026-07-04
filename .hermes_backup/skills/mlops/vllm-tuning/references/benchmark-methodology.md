# Benchmark Methodology (S1, S2, S3)

## Standard Test Suite

Every configuration change should run 3 benchmarks:

### S1: Short Prompt Throughput
- **Goal**: Measure decode throughput, TPOT, inter-token latency
- **Dataset**: random, input_len=128, output_len=128
- **Concurrency**: 10 prompts, inf request rate (all at once)
- **Key metrics**: mean_tpot_ms, output_throughput, request_throughput

### S2: Long Prompt TTFT  
- **Goal**: Measure prefill latency at scale
- **Dataset**: random, input_len=60000, output_len=128
- **Concurrency**: 5 prompts, inf request rate
- **Key metrics**: mean_ttft_ms, median_ttft_ms (watch for median > mean = cache miss)

### S3: Prefix Cache Effectiveness
- **Goal**: Measure caching benefit on shared prefixes
- **Dataset**: prefix_repetition, prefix_len=60000, suffix_len=128, num_prefixes=1
- **Concurrency**: 5 prompts (all share same 60K prefix)
- **Key metrics**: Compare mean_ttft_ms vs S2 (expect ~12x speedup)

## Common Command

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

vllm bench serve --backend openai-chat --endpoint /v1/chat/completions \
  --tokenizer /data/models/deepseekv4_pro --model deepseek_v4_pro \
  --dataset-name <random|prefix_repetition> \
  [dataset-specific params] \
  --num-prompts <N> --request-rate inf --temperature 0 \
  --save-result --result-dir /tmp/vllm_bench --disable-tqdm \
  --result-filename <label>.json
```

## Warmup

First request after restart triggers JIT compilation and CUDA graph capture. ALWAYS warm up:

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek_v4_pro","messages":[{"role":"user","content":"hello"}],"max_tokens":10}'
```

## Metric Interpretation

| Metric | What It Measures | Good | Bad |
|--------|-----------------|------|-----|
| mean_ttft_ms | Average time to first token | <1000 (short prompt) | >5000 |
| median_ttft_ms | Median TTFT | Close to mean (uniform) | >> mean (cache mixed) |
| mean_tpot_ms | Per-token output latency | <50 | >150 |
| mean_itl_ms | Inter-token jitter | Near TPOT | >> TPOT (scheduling issues) |
| output_throughput | Output tokens/second | >200 | <50 |
| request_throughput | Requests/second | >0.5 | <0.1 |

## Data Storage

Results are saved as JSON to `/tmp/vllm_bench_report/`. Key fields in the output:
- `mean_ttft_ms`, `median_ttft_ms`, `p99_ttft_ms`
- `mean_tpot_ms`, `median_tpot_ms`, `p99_tpot_ms`
- `mean_itl_ms`, `median_itl_ms`, `p99_itl_ms`
- `output_throughput`, `request_throughput`, `total_token_throughput`
- `duration`, `completed`, `failed`
