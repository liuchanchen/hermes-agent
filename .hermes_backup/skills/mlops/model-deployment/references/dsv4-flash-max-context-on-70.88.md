# DeepSeek V4 Flash Max Context Length on 70.88 (8× RTX 5090, 32GB)

## Hardware
- 8× NVIDIA GeForce RTX 5090 (32,607 MiB each, Ada architecture)
- Model at `/home/jianliu/work/models/deepseekv4_flash/` (~156 GB, 46 safetensors)
- TP=8 (only viable option — TP<8 OOMs on 32GB cards)

## Binary Search Results

All tests with: TP=8, EP enabled, FP8 KV cache, block-size=256, FULL_AND_PIECEWISE cudagraphs.

| MAX_LEN | gpu_mem_util | Result | KV Available | KV Cache Size | Notes |
|---------|-------------|--------|-------------|---------------|-------|
| 16,384 | 0.92 | ✅ | 1.28 GiB | 26,110 tokens | Baseline |
| 32,768 | 0.92 | ✅ | 1.28 GiB | 48,449 tokens | |
| 65,536 | 0.92 | ✅ | 1.20 GiB | 78,850 tokens | |
| 131,072 | 0.92 | ❌ | 1.20 GiB | — | Need 1.34 GiB |
| 131,072 | 0.95 | ✅ | 2.14 GiB | 225,092 tokens | |
| 262,144 | 0.95 | ✅ | 1.20 GiB | 294,507 tokens | Works but tight |
| 294,912 | 0.95 | ❌ | 1.92 GiB | — | Need 1.97 GiB |
| 294,912 | 0.96 | ✅ | 2.24 GiB | 352,195 tokens | |
| 393,216 | 0.96 | ❌ | 2.08 GiB | — | Need 2.35 GiB |
| 393,216 | 0.97 | ✅ | 2.39 GiB | 417,899 tokens | |
| 282,368 | 0.95 | ✅ | 1.94 GiB | 299,968 tokens | Engine estimate at 0.95 |
| 322,560 | 0.96 | ✅ | 2.18 GiB | 355,966 tokens | Engine estimate at 0.96 |
| 399,616 | 0.97 | ✅ | 2.38 GiB | 418,743 tokens | Engine estimate at 0.97 |
| **412,160** | **0.9735** | ✅ | **2.48 GiB** | **439,660 tokens** | **Bump gpu_mem_util further** |
| 419,584 | 0.9735 | ✅ | 2.47 GiB | 440,589 tokens | |
| **422,656** | **0.9735** | **✅ Final** | **2.46 GiB** | **440,902 tokens** | **Maximum achieved** |
| 425,984 | 0.9735 | ❌ | 2.46 GiB | — | Need 2.47 GiB (barely fails) |
| 425,984 | 0.9738 | ❌ | — | — | Startup fail: 30.53 < 30.54 GiB |
| 435,456 | 0.9735 | ❌ | 2.45 GiB | — | Need 2.51 GiB |
| 458,752 | 0.97 | ❌ | 2.31 GiB | — | Need 2.60 GiB |
| 458,752 | 0.9733 | ❌ | 2.41 GiB | — | Need 2.60 GiB |
| 458,752 | 0.9735 | ❌ | 2.42 GiB | — | Need 2.60 GiB |

## Key Findings

### Maximum max_model_len: 422,656 tokens

At `gpu_memory_utilization=0.9735` (absolute maximum possible on clean 32GB RTX 5090 cards).

### gpu_memory_utilization ceiling

Free memory on a clean RTX 5090 is 32,095 MiB out of 32,607 MiB (32095/32607 ≈ 0.984). However, vLLM startup rejects utilizations that exceed free memory. The precise upper bound found empirically was 0.9735 — at 0.9738 the startup check fails with `Free memory on device cuda:* is less than desired GPU memory utilization`.

### Diminishing returns beyond ~0.96

While 0.96 → 0.97 adds ~150 MB KV cache, the final 0.9735 only adds ~50 MB more. Each increment yields less because CUDA graph memory profiling reserves a fixed chunk proportional to the remaining memory.

### GPU memory breakdown at TP=8 (RTX 5090 32GB)

- Weights: ~19.5 GiB/GPU (156 GB total / 8)
- CUDA graphs + compilation workspace: ~4-5 GiB/GPU
- Activations + overhead: ~2-3 GiB/GPU
- Available for KV cache: ~2.5-3 GiB/GPU at 0.97 gpu_mem_util
- Remaining free: ~0.5-1 GiB (cannot be allocated due to CUDA graph profiling)

### Procedure for Finding Max Context Length

1. **Start at working config** (e.g., MAX_LEN=16384, gpu_mem_util=0.92)
2. **Double MAX_LEN** until the engine reports `ValueError: ... KV cache is needed, which is larger than the available KV cache memory`
3. **Increase gpu_memory_utilization** by 0.01 increments and retry
4. **Binary search** between the last working value and the failed value
5. When startup fails with `Free memory < desired GPU memory utilization`, you've hit the gpu_mem_util ceiling
6. The engine's estimated max model length (from the ValueError message) is often accurate — test it directly

### Restart Cleanup

Between tests, kill all vLLM subprocesses (including `VLLM::` named ones) and wait for GPU memory to return to ~14 MiB:

```bash
ps aux | grep '[v]llm' | awk '{print $2}' | xargs -r kill -9
nvidia-smi --query-compute-apps=pid --format=csv,noheader | sort -u | xargs -r kill -9
sleep 15  # Wait for GPU memory release
```

### Inference Verification

After each successful startup, verify with a simple curl:
```bash
curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"/home/jianliu/work/models/deepseekv4_flash","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```
