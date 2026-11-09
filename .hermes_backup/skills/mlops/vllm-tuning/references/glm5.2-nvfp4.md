# GLM-5.2-NVFP4 on 70.96 (Blackwell 8×96GB)

## Model Info

- **Model ID**: `glm5_2_nvfp4`
- **Path**: `/data/models/glm_5_2_nvfp4/` (47 safetensors, NVFP4 quantized)
- **Architecture**: GlmMoeDsaForCausalLM (256 routed experts, ~800B params, FP8)
- **Server**: vLLM Docker on 10.10.70.96:8000, TP=8, DCP=4, PP=1 (single node)
- **Container image**: `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412`
- **vLLM version**: `v0.19.1rc1.dev29+g93726b2a1.d20260404`
- **KV cache**: **bfloat16** (not fp8) — see critical pitfall below
- **DCP**: decode-context-parallel-size 4 — **incompatible with fp8 KV cache**
- **Prefix caching**: enabled (`--enable-prefix-caching`)
- **Chunked prefill**: enabled (`--enable-chunked-prefill`)
- **Max model len**: 1,048,576 (1M)
- **GPU memory util**: 0.90
- **Max num seqs**: 64
- **Decode context parallel**: 4
- **MoE backend**: b12x
- **Container runtime**: `nvidia` (NOT `warpdrive` — see below)
- **Script**: `/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4.sh` (on 70.96 only)
- **Load time**: ~190s from container start to API readiness (FlashInfer autotune + 19 CUDA graphs)

## Critical Pitfall: DCP + fp8 KV Cache Incompatibility

**The vLLM build in this container (`v0.19.1rc1`) does NOT support `--kv-cache-dtype fp8` together with `--decode-context-parallel-size 4`.**

The error is a hard assert in the worker process:

```
AssertionError: DCP not support fp8 kvcache now.
```

All workers (TP0-7×DCP0-3) fail simultaneously. Engine core reports:

```
RuntimeError: Engine core initialization failed. Failed core proc(s): {}
```

**Fix**: Always use `--kv-cache-dtype bfloat16` when `--decode-context-parallel-size > 1`.

```bash
sed -i 's/--kv-cache-dtype fp8/--kv-cache-dtype bfloat16/' start_glm5_2_nvfp4.sh
```

## Critical Pitfall: Dropping DCP + fp8 → OOM (Not Enough KV Cache Memory)

If you remove `--decode-context-parallel-size 4` to enable fp8, the server will fail with OOM during KV cache allocation:

```
ValueError: To serve at least one request with the model's max seq len (1048576),
(97.8 GiB KV cache is needed, which is larger than the available KV cache memory (28.24 GiB).
Based on the available memory, the estimated maximum model length is 302720.
```

Without DCP, KV cache is not split across GPU pairs, so the 1M context requires 97.8 GiB in a single block. With only 28.24 GiB available per GPU after model weights, this fails. DCP=4 spreads the KV cache across 4 groups of 2 GPUs, making it fit.

## Critical Pitfall: fp8 + No DCP → baddbmm Float8 NotImplementedError

Even if you fix the OOM (by reducing `--max-model-len`), the combination of `--kv-cache-dtype fp8` without DCP triggers a PyTorch CUDA kernel error:

```
NotImplementedError: "baddbmm_cuda" not implemented for 'Float8_e4m3fn'
```

This is a **PyTorch/CUDA limitation** in the container's CUDA runtime — `torch.baddbmm` does not have a float8 kernel for this CUDA version. The attention backend falls through to a code path that tries `baddbmm` with the fp8 KV cache dtype, which crashes.

**There is no workaround in this container image.** The only options are:
1. **Use `--kv-cache-dtype bfloat16`** (with DCP=4 to avoid OOM) — **the only working combo on this image**
2. Use a different vLLM build / container image that has proper fp8 CUDA kernels
3. Use a different base CUDA runtime that supports `baddbmm` with Float8

## Critical Pitfall: `--runtime warpdrive` Not Available

`--runtime warpdrive` is NOT available on 70.96 (or any known server in this cluster). Available runtimes:

```
Runtimes: io.containerd.runc.v2 nvidia runc
Default Runtime: runc
```

Using `--runtime warpdrive` produces:

```
docker: Error response from daemon: unknown or invalid runtime name: warpdrive
```

**Always use `--runtime nvidia`** for GPU workloads:

```bash
# CORRECT:
docker run --gpus all --runtime nvidia IMAGE ...

# Also valid (default runtime uses nvidia-container-toolkit):
docker run --gpus all IMAGE ...
```

## Critical Pitfall: Model Load Takes ~190s — Poll Timeout Must Be Longer

The script's default 180s poll window is **too short** for this model. The load sequence:
1. Model weights loading: ~50s
2. FlashInfer autotuning (fused kernels for TP=8): ~80s
3. CUDA graph capture: 19 PIECEWISE + 11 FULL graphs at various sizes: ~50s
4. Final engine init: ~10s

Total: **~190s** from container start to `/v1/models` responding.

**Fix the script**: Change the poll loop from 90 iterations × 2s to 120 iterations × 2s (240s max):

```bash
for i in $(seq 1 120); do
  if curl -s --connect-timeout 3 --max-time 5 http://localhost:8000/v1/models ...; then
```

Or use a more patient external poll:

```bash
# External poll — fires every 5s until UP
ssh jianliu@10.10.70.96 "for i in \\$(seq 1 120); do
  if curl -s --connect-timeout 3 --max-time 5 http://localhost:8000/v1/models 2>/dev/null | grep -q glm5_2_nvfp4; then
    echo 'UP after ~' \\$((i*5)) 's'; exit 0; fi; sleep 5; done; echo TIMEOUT"
```

## GLM-5.2-NVFP4 MTP2 (Speculative Decoding) Startup

A dedicated MTP-enabled startup script exists at `/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4_mtp2.sh` (also on 70.96 only).

### Critical Pitfall: `--moe-backend b12x` FAILS with MTP Drafter

**The MTP drafter model has unquantized MoE layers.** The `--moe-backend b12x` flag is only supported for **quantized** (NVFP4) MoE. When the main model loads fine with b12x for its NVFP4 layers, the MTP drafter's unquantized MoE layers hit:

```
ValueError: moe_backend='b12x' is not supported for unquantized MoE.
Expected one of ['triton', 'flashinfer_trtllm', 'flashinfer_cutlass', 'aiter'].
```

All workers fail simultaneously. **Fix**: Remove `--moe-backend b12x` from the vLLM args and set `export VLLM_NVFP4_GEMM_BACKEND=b12x` instead. This env var only applies to NVFP4 quantized layers (the main model), leaving the unquantized MTP drafter free to use whatever backend vLLM auto-selects:

- The **NVFP4 main model** → auto-selects `b12x` (via quant method detection from env var)
- The **unquantized MTP drafter** → auto-selects `FlashInfer CUTLASS` (the best available unquantized backend)

### Current Blocker: MTP2 Workers Die After torch.compile

After applying the `--moe-backend b12x` fix, the model loads and MTP drafter initializes successfully. Log shows:

- `Detected MTP model. Sharing target model embedding weights with the draft model.`
- `Using FlashInfer CUTLASS Unquantized MoE backend`
- Model loading: ~44s / 58.26 GiB
- Rank 0 compilation: backbone (~43s) + eagle_head (~3s) + warmup (~15s) = ~62s

However, only 2 vLLM processes survive (API server + EngineCore). The 8 worker processes disappear silently after torch.compile. EngineCore then loops with repeated `No available shared memory broadcast block found in 60 seconds.` every 60s.

**Root cause hypothesis**: Workers 1-7 crash silently during or after their own torch.compile phase (each worker independently compiles the graph), and the EngineCore can't establish shared memory broadcast without them.

**Possible mitigations to try**:
1. Add `--enforce-eager` to skip torch.compile entirely on workers (trade: slower decode perf)
2. Disable compilation for MTP only: not directly configurable via CLI
3. Try without DCP (`--decode-context-parallel-size 1`) to simplify worker topology
4. Set `VLLM_COMPILE_CACHE_ENABLE=0` to skip cached compilation and use eager

## Critical: Benchmark Requires Local Path, Not Model Name

When using `run_vllm_bench_serve.sh` to benchmark this server, the env vars must point to local filesystem paths on 70.96:

| Variable | Correct Value |
|----------|--------------|
| `MODEL` | `/data/models/glm_5_2_nvfp4/` (filesystem path) |
| `TOKENIZER` | `/data/models/glm_5_2_nvfp4/` (filesystem path) |
| `TOKENIZER_MODE` | `deepseek_v4` |
| `SERVED_MODEL_NAME` | `glm5_2_nvfp4` (the model ID from `/v1/models`) |
| `BASE_URL` | `http://127.0.0.1:8000` (local) or `http://10.10.70.96:8000` (remote) |
| `BACKEND` | `openai-chat` |
| `CONCURRENCY` | 32 (match `max-num-seqs`) |

**WRONG** — will hang forever trying to download tokenizer from HF (70.96 has no internet):
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

## CRITICAL: Config `layer_types` Blocks `vllm bench serve`

GLM 5.2's `config.json` contains `\"layer_types\": [\"deepseek_sparse_attention\", ...]` — rejected by transformers strict dataclass validation.

### Fix Option 1 (EASY): `--skip-tokenizer-init` (Recommended for Decode Benchmarks)

**New discovery (2026-07-08)**: The host-side `vllm bench serve` CAN benchmark the GLM-5.2 Docker server using `--skip-tokenizer-init`. This bypasses the host-side config.json validation entirely, letting the server handle all tokenization:

```bash
cd /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test
MODEL=glm5_2_nvfp4 \
TOKENIZER=/data/models/glm_5_2_nvfp4/ \
TOKENIZER_MODE=auto \
TRUST_REMOTE_CODE=1 \
SKIP_CHAT_TEMPLATE=1 \
bash run_vllm_decode_bench_serve.sh --skip-tokenizer-init
```

Note: `MODEL=glm5_2_nvfp4` (the served model name, not filesystem path) works with `--skip-tokenizer-init`. The `TOKENIZER` path still needs a local directory for the benchmark tool's prompt generation.

**Key insight**: The host vLLM binary CAN benchmark the Docker server. The `--skip-tokenizer-init` flag avoids the config.json validation that was the real blocker. Previously documented approaches (patching config.json, running inside Docker, standalone Python scripts) are now **superseded** by this simpler approach for decode-only benchmarking.

**Limitation**: This only works with `run_vllm_decode_bench_serve.sh` (direct `vllm bench serve` invocation). The full `run_vllm_bench_serve.sh` wrapper (cache hit rate support) uses a Python wrapper that also validates config — for that, use the patched config approach.

### Fix Option 2: Patched config.json (Legacy approach)

Create a copy of config.json with `layer_types` removed. See the main SKILL.md for the full procedure.

### Fix Option 3: Standalone Python script (Fallback)

See the "Benchmark via Simple Python Script" section below.

## Custom all_reduce Crash Under Load (WarpDrive TGU)

When running concurrent benchmark traffic against the MTP2 server, the server can crash with:

```
Failed: Cuda error /opt/vllm/csrc/custom_all_reduce.cuh:621 'device-side assert triggered'
```

This is preceded by `ProcessGroupNCCL watchdog thread terminated with exception: CUDA error: device-side assert triggered` on multiple ranks. The crash happens during vLLM's custom PCIe all-reduce kernel, which triggers a GPU device-side assertion on WarpDrive's CUDA compatibility layer.

**Symptoms**:
- Container stays up (`docker ps` shows up) but vLLM API server process crashes
- `/v1/models` and `/health` stop responding
- Last log entries show `custom_all_reduce.cuh:621` error on ranks 3/4/5
- Benchmark requests fail with connection refused

**Fix**: Add `--disable-custom-all-reduce` to vLLM server args:

```bash
  --disable-custom-all-reduce \
```

Trade-off: Slightly higher all-reduce latency, but server won't crash under load on WarpDrive hardware.

## Benchmark via Simple Python Script (When Host/Container vLLM Bench Is Unavailable)

When `vllm bench serve` cannot run — either because `docker exec` is blocked, or the host vLLM build can't parse GLM5 config — use a standalone Python script that hits the OpenAI API endpoint:

```python
import json, time, os
from concurrent.futures import ThreadPoolExecutor
import urllib.request

payload = {
    "model": "glm5_2_nvfp4",
    "messages": [{"role": "system", "content": "You are a helpful assistant."},
                 {"role": "user", "content": "hello " * 512}],
    "max_tokens": 200, "temperature": 0.0, "stream": False,
}

def send(r):
    url = "http://127.0.0.1:8000/v1/chat/completions"
    data = json.dumps(payload).encode()
    start = time.time()
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
        e = time.time() - start
        r = json.loads(body)
        u = r.get("usage", {})
        return {"ok": True, "t": e, "out": u.get("completion_tokens",0), "in": u.get("prompt_tokens",0)}
    except Exception as ex:
        return {"ok": False, "t": time.time()-start, "e": str(ex)[:80]}

with ThreadPoolExecutor(max_workers=16) as p:
    res = list(p.map(send, range(50)))
ok = [r for r in res if r["ok"]]
lats = sorted(r["t"] for r in ok)
print(f"{len(ok)}/{len(res)} ok")
print(f"Req throughput: {len(ok)/sum(r['t'] for r in ok):.1f} req/s")
print(f"TTFT P50: {lats[len(lats)//2]*1000:.0f}ms  P90: {lats[int(len(lats)*0.9)]*1000:.0f}ms")
```

**Key params**: `max_workers=16` (match `max-num-seqs`), `timeout=120` (allow prefill time). TTFT from elapsed time. Throughput = completed / total wall time.

## GPU Status Check on WarpDrive Hardware (70.96)

`nvidia-smi` is NOT functional on WarpDrive servers at either location:

| Location | `nvidia-smi` | `wd-smi` | CUDA |
|----------|-------------|---------|------|
| Host (70.96) | ❌ both paths exit 113 | ✅ `/usr/local/bin/wd-smi` | ✅ WarpDrive compatibility layer |
| Docker container | ❌ exit 113 (stub path) | ❌ not available | ✅ via `--runtime nvidia` |

Commands:
```bash
# Host GPU status:
wd-smi          # summary
wd-smi -L       # list TGUs

# Container GPU: use /metrics endpoint or server log
```

## No Internet Access on 70.96

Node 10.10.70.96 cannot reach HuggingFace or any external network. All model loading, tokenizer access, and package operations must use local paths only. If `vllm bench serve` tries to reach GitHub/HF, it will hang for 3+ minutes before timing out.

## Benchmark Results (2026-07-05)

Concurrency=32, 200 requests per cache rate, 2048→500 tokens, request-rate=inf, 1 warmup run.

```
  cache   shared   unique    done  failed      req/s    out tok/s  total tok/s    mean TTFT    mean TPOT
   0.0%        0     2048     200       0      0.268      133.847      685.295     5146.961ms    205.167ms
  40.0%      819     1229     200       0      0.281      140.568      719.707     4284.635ms    195.278ms
  80.0%     1638      410     200       0      0.277      138.426      708.739     6143.636ms    194.806ms
```

Zero failures across 600 requests. ~195-205ms TPOT stable. No cache hit benefit at conc=32 because `max-num-seqs=32` matches concurrency, minimizing scheduling benefits from prefix caching.

## Benchmark Results (2026-07-07 — MTP2, Simple Python Script)

MTP2 enabled, 1024 input→200 output tokens, 50 requests, concurrency=16, no warmup. Server crashed during benchmark with `custom_all_reduce.cuh:621 device-side assert`.

```
  glm5_2_nvfp4 MTP2 Benchmark (42/50 ok)
==================================================================
  Duration:       94.9s
  Req throughput: 0.4 req/s
  Out throughput: 21 tok/s
  Total tok/s:    257 tok/s
  TTFT P50:       27127ms
  TTFT P90:       52432ms
  TTFT P99:       85813ms
  Failed: 8
```

TTFT is very high (~27s median) and throughput low. The server also crashed partway through (42/50 completed). Likely causes: MTP2 speculation rejects adding overhead, and the custom_all_reduce kernel assertion killed some ranks. Next steps: add `--disable-custom-all-reduce` and re-benchmark.

### Patching Script (Reproducible)

```bash
python3 -c "
import json, shutil, sys
from pathlib import Path
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/data/models/glm_5_2_nvfp4/')
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/tmp/glm5_bench_patch')
if dst.exists(): shutil.rmtree(dst)
dst.mkdir(parents=True)
cfg = json.loads((src / 'config.json').read_text())
cfg.pop('layer_types', None)
(dst / 'config.json').write_text(json.dumps(cfg, indent=2))
for pat in ['tokenizer*', '*vocab*', '*merges*', 'added_tokens*', 'special_tokens*', 'chat_template*', 'generation_config*']:
    for f in src.glob(pat): shutil.copy2(f, dst / f.name)
print(dst)
"
```
