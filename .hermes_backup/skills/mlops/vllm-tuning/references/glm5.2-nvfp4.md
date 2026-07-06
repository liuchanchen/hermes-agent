# GLM-5.2-NVFP4 on 70.96 (Blackwell 8×96GB)

## Model Info

- **Model ID**: `glm5_2_nvfp4`
- **Path**: `/data/models/glm_5_2_nvfp4/` (47 safetensors, NVFP4 quantized)
- **Architecture**: GlmMoeDsaForCausalLM (256 routed experts, ~800B params, FP8)
- **Server**: vLLM on 10.10.70.96:8000, TP=8, DP=0, PP=1 (single node)
- **KV cache**: bfloat16 (not fp8) — `--kv-cache-dtype bfloat16`
- **Prefix caching**: enabled (`--enable-prefix-caching`)
- **Chunked prefill**: enabled (`--enable-chunked-prefill`)
- **Max model len**: 1,048,576 (1M)
- **GPU memory util**: 0.90
- **Max num seqs**: 32
- **Decode context parallel**: 4
- **Tool-call parser**: glm47
- **Reasoning parser**: glm45
- **MoE backend**: b12x
- **Other flags**: `--chat-template-content-format=string --enable-auto-tool-choice`

## Server Startup Command

From `ps aux`:
```
python3 -m vllm.entrypoints.openai.api_server \
  --model /data/models/glm_5_2_nvfp4/ \
  --host 0.0.0.0 --port 8000 \
  --served-model-name glm5_2_nvfp4 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --decode-context-parallel-size 4 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 32 \
  --kv-cache-dtype bfloat16 \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --tool-call-parser glm47 \
  --chat-template-content-format=string \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --moe-backend b12x
```

## Critical: Benchmark Requires Local Path, Not Model Name

When using `run_vllm_bench_serve.sh` to benchmark this server, the `MODEL`, `TOKENIZER`, and `SERVED_MODEL_NAME` env vars must be set correctly:

| Variable | Correct Value |
|----------|--------------|
| `MODEL` | `/data/models/glm_5_2_nvfp4/` (filesystem path) |
| `TOKENIZER` | `/data/models/glm_5_2_nvfp4/` (filesystem path) |
| `TOKENIZER_MODE` | `deepseek_v4` |
| `SERVED_MODEL_NAME` | `glm5_2_nvfp4` (the model ID from `/v1/models`) |
| `BASE_URL` | `http://127.0.0.1:8000` (local) or `http://10.10.70.96:8000` (remote) |
| `BACKEND` | `openai-chat` |
| `CONCURRENCY` | 32 (default max-num-seqs on this server) |

**WRONG** — will hang forever trying to download tokenizer from HF:
```bash
MODEL=glm5_2_nvfp4 TOKENIZER=glm5_2_nvfp4 bash run_vllm_bench_serve.sh
```

**CORRECT** — uses local model directory for tokenizer:
```bash
MODEL=/data/models/glm_5_2_nvfp4/ \
TOKENIZER=/data/models/glm_5_2_nvfp4/ \
TOKENIZER_MODE=deepseek_v4 \
SERVED_MODEL_NAME=glm5_2_nvfp4 \
BASE_URL=http://127.0.0.1:8000 \
BACKEND=openai-chat \
CONCURRENCY=32 \
bash run_vllm_bench_serve.sh
```

## CRITICAL: Config `layer_types` Blocks `vllm bench serve` (Even with Correct Paths)

Even with local paths set correctly, `vllm bench serve` will crash at startup because GLM 5.2's `config.json` contains:

```json
"layer_types": ["deepseek_sparse_attention", "deepseek_sparse_attention", ...]
```

This value is rejected by `transformers` strict dataclass validation (`validate_layer_type`). The error:

```
huggingface_hub.errors.StrictDataclassClassValidationError: Class validation error
  for validator 'validate_layer_type':
    ValueError: The `layer_types` entries must be in ('full_attention',
    'sliding_attention', ...) but got ['deepseek_sparse_attention', ...]
```

**The vLLM API server itself works fine** — vLLM uses its own config parser that doesn't validate layer types. Only `vllm bench serve` crashes because it loads config via `transformers.AutoConfig.from_pretrained`.

**Fix**: Create a patched copy of the model directory with `layer_types` removed from config.json. Point both `MODEL` and `TOKENIZER` to the patched directory:

```bash
python3 -c "
import json, shutil
from pathlib import Path
src = Path('/data/models/glm_5_2_nvfp4/')
dst = Path('/tmp/glm5_bench_patch')
cfg = json.loads((src / 'config.json').read_text())
cfg.pop('layer_types', None)
(dst / 'config.json').write_text(json.dumps(cfg, indent=2))
for pat in ['tokenizer*', '*vocab*', '*merges*', 'added_tokens*',
            'special_tokens*', 'chat_template*', 'generation_config*']:
    for f in src.glob(pat):
        shutil.copy2(f, dst / f.name)
"

MODEL=/tmp/glm5_bench_patch \
TOKENIZER=/tmp/glm5_bench_patch \
TOKENIZER_MODE=deepseek_v4 \
SERVED_MODEL_NAME=glm5_2_nvfp4 \
BASE_URL=http://127.0.0.1:8000 \
BACKEND=openai-chat \
CONCURRENCY=32 \
bash run_vllm_bench_serve.sh

# Cleanup:
rm -rf /tmp/glm5_bench_patch
```

## No Internet Access on 70.96

Node 10.10.70.96 cannot reach HuggingFace or any external network. All model loading, tokenizer access, and package operations must use local paths only. If `vllm bench serve` tries to reach GitHub/HF, it will hang for 3+ minutes before timing out and may take down the whole process.

## Benchmark Duration Warning

At CONCURRENCY=32 with 200 requests × 3 cache hit rates, the benchmark takes longer than 600 seconds (exceeds foreground terminal timeout). Use background launch pattern (SSH `setsid` or `nohup`) when running.

## Benchmark Results (2026-07-05)

Benchmark run via `run_vllm_bench_serve.sh` with patched config (layer_types removed). Concurrency=32, 200 requests per cache rate, 2048→500 tokens, request-rate=inf, 1 warmup run.

```
==============================================================================================================================
glm5_2_nvfp4 vLLM Bench Serve Summary
==============================================================================================================================
  cache   shared   unique    done  failed      req/s    out tok/s  total tok/s    mean TTFT    mean TPOT
------------------------------------------------------------------------------------------------------------------------------
   0.0%        0     2048     200       0      0.268      133.847      685.295     5146.961ms    205.167ms
  40.0%      819     1229     200       0      0.281      140.568      719.707     4284.635ms    195.278ms
  80.0%     1638      410     200       0      0.277      138.426      708.739     6143.636ms    194.806ms
==============================================================================================================================
```

**Key observations:**
- **Zero failures** across all 600 requests — server stable
- **~0.27-0.28 req/s** throughput, consistent across cache rates
- **~195-205ms TPOT** — very stable, decode-bound
- **TTFT varies but is surprisingly high at 80% cache** (6.1s vs 4.3s at 40%). This is likely because the `random` dataset with 80% shared prefix (1638 shared tokens) generates a long common prefix that must be prefilled before unique suffixes, and the server's `max-num-seqs=32` limits concurrent prefill scheduling.
- **No cache hit benefit visible at concurrency=32** on this server because `max-num-seqs=32` matches concurrency — the server can handle all 32 concurrent requests without queuing, so prefix caching's scheduling benefit is minimal. Higher concurrency (>32) would show larger TTFT improvements from caching.

### Benchmark Executions (Background via Setup Script)

To run the benchmark on a networked server (no HuggingFace access) with a GLM model whose config triggers transformers validation, the following approach is verified working:

1. **Write a Python script** on the remote host that creates a patched config dir (removes `layer_types` from `config.json`, copies tokenizer files)
2. **Export env vars** pointing both `MODEL` and `TOKENIZER` to the patched dir
3. **Run via `bash run_vllm_bench_serve.sh`** (not direct `vllm bench serve`) inside the benchmark directory
4. **Cleanup** the patched dir after completion

The patched dir IS ephemeral and the original model dir is never modified.

### Timing Profile per Cache Rate

Each cache rate benchmark at concurrency=32 roughly follows this pattern:
- **Warmup**: ~14-15s per request (single sequential request)
- **Main run (200 requests)**: ~11-13 min total, with phases:
  - First few requests: very slow (~100s/request) while KV cache cold
  - Mid-run (~50-150/200): faster (~1-2s/request) as prefills batch
  - Tail (192-200/200): slow again (~7-8s/request) as scheduler serializes
- **Total for all 3 rates**: ~35-45 minutes

### Patching Script (Reproducible)

The small Python script that creates the patched config dir:

```bash
python3 -c "
import json, shutil, sys
from pathlib import Path
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/data/models/glm_5_2_nvfp4/')
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/tmp/glm5_bench_patch')
if dst.exists():
    shutil.rmtree(dst)
dst.mkdir(parents=True)
cfg = json.loads((src / 'config.json').read_text())
cfg.pop('layer_types', None)
(dst / 'config.json').write_text(json.dumps(cfg, indent=2))
for pat in ['tokenizer*', '*vocab*', '*merges*', 'added_tokens*', 'special_tokens*', 'chat_template*', 'generation_config*']:
    for f in src.glob(pat):
        shutil.copy2(f, dst / f.name)
print(dst)
"
```
