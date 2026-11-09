# GLM-5.2-NVFP4 b12x/Sparse Attention Startup (70.96)

The script `start_glm5_2_nvfp4_sparse_b12x.sh` on 70.96 starts GLM-5.2-NVFP4 with **sparse attention + b12x MoE backend** in Docker.

## Docker Image

| Image | Tag | Where |
|-------|-----|-------|
| `voipmonitor/vllm:fathomless-firmament-v16-vllm8f86f42-b12xfe06f49-fi801d57a-cu132-20260714` | v16/b12x | 70.96 ✅, 12.12 ❌ |
| `voipmonitor/vllm:gilded-gnosis-v18-vllm264bce1-b12xbc85ef3-fi801d57a-cu132-20260718` | v18/b12x (newer) | 70.96 ✅ |
| `10.10.91.56/sw2/vllm-glm:fathomless-firmament-v16-vllm8f86f42-b12xfe06f49-fi801d57a-cu132-20260714` | Internal registry | 70.96 ✅ (same image, different tag) |
| `voipmonitor/vllm:preserve-glm51-hotfix-mtp5-prob-327279b-20260412` | Non-MTP, non-b12x | 70.96 ✅ |

**192.168.12.12 has NO vLLM images** — only `ghcr.io/openlit/openlit:latest`. To run b12x on 12.12, the image must be pulled/pushed first.

## Key Script Parameters (vs Non-MTP)

| Parameter | b12x/Sparse | Non-MTP (preserve-glm51) |
|-----------|------------|------------------------|
| MoE backend | `--moe-backend b12x` | Default (aiter) |
| KV cache dtype | `auto` (bf16) | `auto` (bf16) |
| Custom all-reduce | `--disable-custom-all-reduce` | Not disabled |
| Decode ctx parallel | 1 | 4 (DCP=4) |
| Sparse attention | Enabled (default from config) | Enabled |
| Max model len | 262144 | 870400 |
| GPU mem util | 0.82 | 0.87 |
| Max num seqs | 64 | 16 |
| Prefix caching | `--enable-prefix-caching` | `--enable-prefix-caching` |
| Chunked prefill | `--enable-chunked-prefill` | Not set |
| Reasoning parser | `--reasoning-parser glm45` | — |
| Tool call parser | `--tool-call-parser glm47` | — |
| Auto tool choice | `--enable-auto-tool-choice` | — |
| Port | 18021 | 8000 |

## Docker Details

- **Container name**: `{USER}_glm52_nvfp4_b12x_mtp0_p18021_{YYYYMMDD}`
- **Host workdir**: Mounted at `/workspace` inside container
- **Model dir**: `/data/models/glm_5_2_nvfp4/` (local on 70.96)
- **Startup log**: `/data/model_startup_script/{CONTAINER_NAME}_docker.log`
- **vLLM log**: `/data/model_startup_script/{CONTAINER_NAME}_vllm.log`
- **Triton cache**: `/data/triton_cache/{CONTAINER_NAME}`
- **Torch cache**: `/data/torch_cache/{CONTAINER_NAME}`
- **Entrypoint**: Sleep infinity, then `docker exec` to start vLLM (not `docker run` with direct command)

## Startup Sequence

```bash
# Script path on 70.96:
/home/jianliu/work/tgu01-pro-model-deployment/glm5_2_nvfp4/start_glm5_2_nvfp4_sparse_b12x.sh
```

The script:
1. Re-execs without LD_PRELOAD
2. Creates container with `sleep infinity` as entrypoint
3. Stops any stale vLLM process inside the container
4. Copies a generated `start_vllm.sh` script into the container
5. Execs the start script in the background via `docker exec -d`
6. Waits up to 900s for `/v1/models` to report the served model name

## Container Reuse

If a container with the same name already exists:
- **Same image**: Reuses it (starts if stopped)
- **Different image**: Exits with error code 2

## b12x vs Default MoE Backend

The `--moe-backend b12x` flag uses the Block-wise 12-way MoE kernel. This is different from `aiter` (the default for the preserve-glm51 image) or `triton` or `marlin`. On b12x images:

- Cannot use MTP speculative decoding (MTP's drafter has unquantized MoE layers incompatible with b12x)
- Likely not compatible with `--kv-cache-dtype fp8` (uses `auto`/bf16)
- The `--disable-custom-all-reduce` suggests custom_all_reduce may crash on WarpDrive TGU (SM 12.0) — confirmed in earlier testing

## Image Cache Note

On 70.96, the image `10.10.91.56/sw2/vllm:fathomless-firmament-v16...` and `10.10.91.56/sw2/vllm-glm:fathomless-firmament-v16...` both exist as separate tagged images with the same underlying layers. The `sw2/vllm-glm` variant may have GLM-specific additions.
