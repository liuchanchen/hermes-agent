# vLLM Throughput & TTFT Optimization Guide

Systematic approach to tuning vLLM serving parameters for optimal throughput and Time-to-First-Token (TTFT), based on DeepSeek V4 Pro deployment on a 2-node TP=8+DP=2+EP=16 cluster (RTX 5090 + RTX PRO 6000 Blackwell SE).

## Standardized Measurement Tool

Use `vllm bench serve` with these exact parameters:

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
vllm bench serve --host localhost --port 8000 \
  --endpoint /v1/chat/completions \
  --backend openai-chat \
  --model <model-name> \
  --tokenizer </path/to/model> \
  --temperature 0 \
  --request-rate inf \
  --save-result --result-dir /tmp/vllm_bench \
  --disable-tqdm
```

**Critical flags**:
- `--backend openai-chat` — without this, the benchmark sends raw text completions, resulting in `Bad Request`
- `--endpoint /v1/chat/completions` — must match the server's endpoint
- `--tokenizer` — local path to avoid HuggingFace downloads (required on offline servers)
- `--temperature 0` — greedy decoding for deterministic benchmarking
- `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` — prevents network timeouts on offline servers

## Key Metrics (from vllm bench serve output)

| Metric | Full Name | What It Measures | Target |
|--------|-----------|-------------------|--------|
| **TTFT** | Time to First Token | Prefilling time (entire input processed + first decode token) | Minimize for user-perceived latency |
| **TPOT** | Time Per Output Token | Time for each generated token after first | Minimize for generation speed |
| **ITL** | Inter-token Latency | Wall-clock gap between successive tokens in streaming | ~TPOT (lower is better) |
| **Request Throughput** | req/s | Requests per second | Maximize |
| **Output Token Throughput** | tok/s | Generated tokens per second | Maximize |

## Parameter Optimization Matrix

### `max-num-batched-tokens` × `max-num-seqs`

These two parameters interact directly. The relationship:
- **batched-tokens ≈ seqs × avg_seq_len** — they must be balanced
- Larger batched-tokens → prefill processes more tokens per scheduler step, faster prefill for long prompts
- Smaller batched-tokens → more granular chunked prefill, lower TTFT under concurrent load

**Recommended scan** (each needs a server restart):

| # | batched-tokens | max-num-seqs | compile_ranges_endpoints | TTFT (short prompt) | TTFT (long prompt 60K) | Output Throughput |
|---|---------------|-------------|------------------------|--------------------|----------------------|-------------------|
| 1 | **16384** | **256** | [8192,16384] | ~1.3s | ~285s | ~105 tok/s |
| 2 | **8192** | **128** | [8192] | Lowest (<1s expected) | Highest (more chunking) | Lower |
| 3 | **8192** | **512** | [8192] | Low | High (contention) | Moderate |
| 4 | **32768** | **128** | [8192,16384,32768] | Higher | Lower (~200s) | Higher |
| 5 | **32768** | **256** | [8192,16384,32768] | High | Moderate | Highest |
| 6 | **65536** | **64** | [8192,16384,32768,65536] | High | Lowest (min chunking) | Moderate |

**Startup timeout caveat**: On the vLLM ds4-sm120 branch, EngineCore startup has a hard 300-second timeout. `max-num-batched-tokens=32768` with default `max-num-seqs=512` can exceed this timeout. Reducing to `max-num-batched-tokens=16384` + `max-num-seqs=256` reliably succeeds.

### `max-num-seqs` and KV Cache

`max-num-seqs` does NOT control KV cache sizing — that's driven by `max-model-len` and `block-size`. However, reducing `max-num-seqs` can free memory for other purposes in memory-constrained environments.

### `request-rate` (benchmark parameter, no restart needed)

| rate | Behavior | TTFT | Throughput |
|------|----------|------|------------|
| inf | All requests fire simultaneously, max queue contention | Highest | Highest |
| 1.0 | 1 req/s, steady Poisson arrival | Moderate | Moderate |
| 0.5 | 1 req per 2s, no queue buildup | Lowest (no queuing) | Lower |

## Prefix Cache Testing

Use the `prefix_repetition` dataset for controlled prefix cache experiments:

```bash
# 100% cache hit (all requests share same 60K prefix)
vllm bench serve ... \
  --dataset-name prefix_repetition \
  --prefix-repetition-prefix-len 60000 \
  --prefix-repetition-suffix-len 128 \
  --prefix-repetition-num-prefixes 1 \
  --num-prompts 5

# 50% cache hit (shared prefix + unique suffix)
vllm bench serve ... \
  --dataset-name prefix_repetition \
  --prefix-repetition-prefix-len 30000 \
  --prefix-repetition-suffix-len 30000 \
  --prefix-repetition-num-prefixes 5 \
  --num-prompts 10

# 0% cache hit (no shared prefix)
vllm bench serve ... \
  --dataset-name prefix_repetition \
  --prefix-repetition-prefix-len 0 \
  --prefix-repetition-suffix-len 60000 \
  --prefix-repetition-num-prefixes 5 \
  --num-prompts 5
```

The request structure is: `input = [shared prefix] + [unique suffix]` where `num-prefixes` controls how many different shared prefixes exist. With `num-prefixes=1`, all requests share 100% of the prefix, maximizing cache hits.

## Compilation Modes

| mode | Description | Startup Time | Runtime Performance |
|------|-------------|-------------|-------------------|
| mode=3 + cudagraph FULL_AND_PIECEWISE | Torch Inductor compile + CUDA graphs | Slowest (5-10 min) | Best |
| mode=0 + cudagraph | CUDA graphs only (no torch.compile) | Medium | Good |
| enforce-eager | No compilation | Fastest | Worst |

## Common Pitfalls

1. **`--backend openai-chat` is mandatory** — `--endpoint /v1/chat/completions` alone is insufficient
2. **100% cache hit TTFT is NOT 0** — first request must still do full prefill; only subsequent requests benefit
3. **`vllm bench serve` needs LOCAL `--tokenizer` on offline servers** — must also set HF_HUB_OFFLINE=1
4. **Batch TTFT scales with concurrent requests** — 10 concurrent requests with 128 input each has higher TTFT than 1 request, because all 10 must be prefilled first
5. **Mixed GPU HBM sizes cause cluster-level failures** — the worker with less HBM will fail KV cache profiling even if the master succeeds

## Reference Numbers (DeepSeek V4 Pro, TP=8 DP=2 EP=16)

| Scenario | Input | Output | Concurrency | TTFT | TPOT | Throughput |
|----------|-------|--------|-------------|------|------|------------|
| Short prompt | 128 | 128 | 10 | ~1.3s | ~84ms | ~105 tok/s |
| Long prompt (no cache) | 60K | 128 | 5 | ~285s | ~1.3s | ~1.4 tok/s |
| Short (via Python requests) | ~10 | 256 | 20 | ~244ms | ~55ms | ~285 tok/s |
