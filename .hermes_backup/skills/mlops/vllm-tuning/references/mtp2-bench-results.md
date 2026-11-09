# MTP2 Benchmark Results — GLM-5.2-NVFP4 on 70.96

## Server Config

- **Model**: GLM-5.2-NVFP4 (TP=8, DCP=4, bf16 KV cache)
- **Hardware**: WarpDrive TGU x8 (95 GiB each), SM 12.0
- **Container**: `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412`
- **MTP2**: `--speculative-config '{"method":"mtp","num_speculative_tokens":2}'`
- **Script**: `/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4_mtp2.sh`

## Round 1: OOM + custom_all_reduce Crash (2026-07-07)

Params: `max-num-seqs=64`, `gpu-memory-utilization=0.90`, `max-model-len=1048576`

Standalone Python script benchmark — 1024 input → 200 output tokens, 50 requests, concurrency=16.

```
glm5_2_nvfp4 MTP2 Benchmark (42/50 ok)
  Duration:       94.9s
  Req throughput: 0.4 req/s
  Out throughput: 21 tok/s
  Total tok/s:    257 tok/s
  TTFT P50:       27127ms (27.1s)
  TTFT P90:       52432ms (52.4s)
  TTFT P99:       85813ms (85.8s)
  Failed: 8
```

**Crashes**:
- `MemoryError: CUDA out of memory. Tried to allocate 54.00 MiB. GPU 0 has a total capacity of 94.97 GiB of which 30.88 MiB is free.`
- `Failed: Cuda error /opt/vllm/csrc/custom_all_reduce.cuh:621 'device-side assert triggered'`

Root causes: 1M context len + 64 concurrent seqs filled all GPU memory. Custom all-reduce kernel assertion on WarpDrive TGU's CUDA compat layer.

## Round 2: Recovered but Slow with max-num-seqs=32 (2026-07-08)

After reducing to `max-num-seqs=32`, `gpu-memory-utilization=0.90`, `max-model-len=870400`.

Standalone Python script — 1024 input → 200 output tokens, 100 requests, concurrency=16.

```
glm5_2_nvfp4 MTP2 Benchmark (100/100 ok)
  Duration:         226.1s
  Req throughput:   0.44 req/s
  Out throughput:   24.7 tok/s
  Total throughput: 259 tok/s
  TTFT P50:  29099ms  (29.1s)
  TTFT P90:  58283ms  (58.3s)
  TTFT P95:  75802ms  (75.8s)
  TTFT P99:  124040ms (124s)
  Mean:      34967ms  (35.0s)
  TPOT P50:  711.8ms/tok (1.40 tok/s)
  TPOT P90:  357.7ms/tok (2.80 tok/s)
  TPOT P99:  208.8ms/tok (4.79 tok/s)
  Mean:      581.9ms/tok (1.72 tok/s)
```

## Round 3: OOM during vllm bench serve (2026-07-08)

After reducing to `max-num-seqs=32`, `gpu-memory-utilization=0.87`, `max-model-len=870400`.

The benchmark failed silently during the OOM earlier (`gpu-memory-utilization=0.87` wasn't enough with 870400 model len). Server log shows:

```
MemoryError: CUDA out of memory. Tried to allocate 1.51 GiB. GPU 3 has a total capacity of 94.97 GiB of which 682.88 MiB is free.
```

Model weights = ~58 GiB. The remaining ~37 GiB is consumed by KV cache pre-allocation at 870400 context.

## Round 4: vllm bench serve from Host via Config Patch (2026-07-08)

**Major finding: `vllm bench serve` CAN run from the HOST with a patched config.json.**

The host's `vllm bench serve` (at `/data/venvs/vllm-ds4/bin/vllm`) failed to initialize because the installed `transformers`/`huggingface_hub` strictly validates `config.json` `layer_types` against a known allowed set, and `deepseek_sparse_attention` is not in that set.

**Fix**: Create a patched copy of the model's `config.json` with `layer_types` removed, and point both `--model` and `--tokenizer` to the patched directory:

```bash
python3 -c "
import json, shutil; from pathlib import Path
src = Path('/data/models/glm_5_2_nvfp4/')
dst = Path('/tmp/glm5_tokenizer')
cfg = json.loads((src / 'config.json').read_text())
cfg.pop('layer_types', None)
(dst / 'config.json').write_text(json.dumps(cfg, indent=2))
for pat in ['tokenizer*', '*vocab*', '*merges*', 'added_tokens*',
            'special_tokens*', 'chat_template*', 'generation_config*']:
    for f in src.glob(pat): shutil.copy2(f, dst / f.name)
"
```

**IMPORTANT**: The host tool sends HTTP requests to port 8000 via the Docker container's vLLM API server. No `docker exec` needed.

**Server config for this round**: `num_speculative_tokens=1` (was 2), `gpu-memory-utilization=0.87`, `max-model-len=870400`, `max-num-seqs=32`

**Benchmark default params**: REQUESTS=200, CONCURRENCY=64, INPUT_TOKENS=2048, OUTPUT_TOKENS=500, WARMUPS=1, CACHE_HIT_RATES=0,0.4,0.8, REQUEST_RATE=inf

### Cache 0% — 200/200 completed ✅

| Metric | Value |
|--------|-------|
| Duration | 1004.7s |
| Request throughput | 0.20 req/s |
| Output throughput | 99.5 tok/s |
| Total token throughput | 509.6 tok/s |
| MTP2 acceptance rate | 53.1% |
| MTP2 acceptance length | 1.53 |
| TTFT P50 | 148,222ms |
| TTFT P90 | 159,246ms |
| TTFT P99 | 174,335ms |
| TPOT P50 | 295ms/tok (3.4 tok/s) |
| TPOT P90 | 317ms/tok |
| Mean ITL | 446ms |
| Mean E2EL | 274s |

### Cache 40% — 64/200 completed ❌ (server crashed)

Server crashed with OOM partway through the second cache rate run. Same OOM pattern as Round 3 — 870400 model len consumed too much KV cache.

Server metrics during healthy load (cache 0% run):
```
Avg prompt throughput: 2057.0 tokens/s  (during prefill bursts)
Avg generation throughput: 91.9 tokens/s
Running: 32 reqs, Waiting: 32 reqs
GPU KV cache usage: 8.6%
Prefix cache hit rate: 1.0%
SpecDecoding: Mean acceptance length: 1.47-1.55
  Per-position acceptance rate: 0.406-0.562
  Avg Draft acceptance rate: 40.6%-56.2%
```

## Three Failure Modes (Comprehensive)

| Failure | Error | Cause | Fix |
|---------|-------|-------|-----|
| **OOM** | `CUDA out of memory. Tried to allocate N MiB. Only X MiB free.` | 870K context pre-allocates too much KV cache | Reduce `--max-model-len` to 16K-32K for benchmark, or reduce `--gpu-memory-utilization` to 0.80 |
| **DCP+fp8 assert** | `AssertionError: DCP not support fp8 kvcache now.` | Model config overrides CLI kv-cache-dtype | Ensure `--kv-cache-dtype bfloat16` in CMD (not overridden) |
| **custom_all_reduce** | `Cuda error custom_all_reduce.cuh:621 device-side assert` | WarpDrive TGU CUDA compat layer | Add `--disable-custom-all-reduce` |

## Key Learnings (updated 2026-07-08)

1. **MTP2 acceptance rate is ~43-56%** (num_spec_tokens=2 → ~43%; num_spec_tokens=1 → ~47-56%) — marginal improvement, speculative decoding adds overhead
2. **TTFT is dominated by prefill** at 870K max-model-len (mean TTFT = 35-148s) — reducing to 16K would dramatically improve latency
3. **GPU memory is the binding constraint**: model weights ~58 GiB leaves only ~37 GiB for KV cache across 8 GPUs
4. **custom_all_reduce crashes** under load on WarpDrive TGU — always add `--disable-custom-all-reduce`
5. **`vllm bench serve` CAN work from host** with a patched `config.json` — the `/tmp/glm5_tokenizer` trick is reliable
6. **`gpu-memory-utilization=0.87` is still too high** for 870K model len with MTP2 — use 0.85 or lower, or reduce model len to 16K for benchmark runs
7. **cuda graph capture** adds ~20s to startup
8. **Benchmark at concurrency=64 with max-num-seqs=32** creates a long queue (32 running, 32 waiting). Expected behavior on this setup. Benchmark runtime ~15-20 min for 200 requests.

## vllm bench serve Workflow for GLM5 on 70.96

**Working command** (from host):

```bash
# 1. Create patched tokenizer once
mkdir -p /tmp/glm5_tokenizer
python3 -c "
import json, shutil; from pathlib import Path
src = Path('/data/models/glm_5_2_nvfp4/')
dst = Path('/tmp/glm5_tokenizer')
cfg = json.loads((src / 'config.json').read_text())
cfg.pop('layer_types', None)
(dst / 'config.json').write_text(json.dumps(cfg, indent=2))
for pat in ['tokenizer*', '*vocab*', '*merges*', 'added_tokens*',
            'special_tokens*', 'chat_template*', 'generation_config*']:
    for f in src.glob(pat): shutil.copy2(f, dst / f.name)
"

# 2. Run benchmark (default params)
cd ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test
MODEL=/data/models/glm_5_2_nvfp4/ \
TOKENIZER=/tmp/glm5_tokenizer \
TOKENIZER_MODE=auto \
SERVED_MODEL_NAME=glm5_2_nvfp4 \
BACKEND=openai-chat \
MODEL_LABEL=glm5_2_nvfp4_mtp2 \
bash run_vllm_bench_serve.sh
```

**Key insight**: `TOKENIZER_MODE=auto` works with the patched config. `deepseek_v4` is NOT needed — the GLM5 tokenizer is a standard HuggingFace tokenizer.
