# 10.10.70.88 — Primary Dev Server Detailed Setup

**GPU:** 8× NVIDIA RTX 5090 (Blackwell, CC 12.0, 32GB)
**Driver:** 580.126.09 | **CUDA Driver:** 13.0 | **CUDA Toolkit:** 13.0.88 (nvcc only)
**System:** Ubuntu 22.04 LTS | **Kernel:** (default)

## Key Environment

- **Proxy:** `http://10.10.60.140:7890` (in ~/.bashrc)
- **NCCL:** 2.28.9-1+cuda13.0
- **vLLM fork:** `/data/vllm-ds4-sm120/` (jasl/vllm ds4-sm120, v0.6.0.dev0)
- **venv:** `/data/venvs/vllm-ds4/` (Python 3.12, PyTorch 2.11.0+cu130)
- **Model path:** `/home/jianliu/work/models/deepseekv4_flash/`
- **Work directory:** `~/work/bandwidth_test/`

## Proxy & Internet Access

- **Proxy:** `http://10.10.60.140:7890` (in ~/.bashrc)
- **HuggingFace.co:** ❌ **Connection timeout** during non-interactive SSH sessions — curling `huggingface.co` fails with `Failed to connect to huggingface.co port 443: Connection timed out`
- **hf-mirror.com:** ❌ Also unreachable (same timeout)
- **PyPI:** ❌ `pip install` times out with `ReadTimeoutError`
- **Key implication:** Models and Python packages CANNOT be downloaded directly on 70.88. Use the **relay pattern**: download to a machine with internet access, then `rsync` to 70.88
- **rsync relay speed:** Between WSL and 70.88 via LAN, expect 50-120 MB/s

## SSH (proxy required)

```
ssh -t jianliu@10.10.70.88 "source ~/.bashrc && command"
```

Non-interactive SSH does NOT load .bashrc — always source it first.

## nccl-tests

Compiled at `~/work/bandwidth_test/nccl-tests/build/`.
Makefile auto-detects CUDA and sm_120 support.

## Reference 8-card bandwidth

| Operation | Large Data (>128MB) |
|-----------|---------------------|
| all_reduce | 22-23 GB/s (Algo) / 39-40 GB/s (Bus) |

## Performance Profiling Tools (2026-06-25)

### perf

Already installed via `linux-tools-6.8.0-111-generic`. Matches kernel 6.8.0-111.
```bash
perf --version
# perf version 6.8.12
```

### Intel PCM

Built from source (apt package `pcm` 202201-1 too old — doesn't support Emerald Rapids Xeon Platinum 8558P).

```bash
curl -sL "https://github.com/intel/pcm/archive/refs/heads/master.tar.gz" -o /tmp/pcm.tar.gz
cd /tmp && tar xzf pcm.tar.gz && cd pcm-master && mkdir build && cd build
cmake .. && make -j$(nproc) && sudo make install
```

Binaries at `/usr/local/sbin/pcm*`. Requires sudo for MSR access.

## Docker image available

`vllm/vllm-openai:latest` can be used for quick deployment without source compilation.

## Qwen-Image-2512 Diffusion Server

**Model:** `/data/models/qwen_image_2512/` (Qwen/Qwen-Image-2512, diffusion text-to-image)
**venv:** `/data/venvs/vllm-ds4/`
**Port:** 8000
**Startup script:** `/tmp/qwen_image_server.py`

### Architecture: vLLM CANNOT serve this model

`vLLM` only serves **autoregressive causal language models** (text completion, chat). Qwen-Image-2512 is a **diffusion image generation pipeline** (`QwenImagePipeline`, 60-layer transformer + VAE + Qwen2.5-VL text encoder). It requires `diffusers` + FastAPI instead.

### Dependencies
```bash
/data/venvs/vllm-ds4/bin/pip install diffusers accelerate
```
Already installed: `diffusers 0.38.0`, `accelerate 1.13.0`, `fastapi`, `uvicorn`, `pillow`, `safetensors`.

### Starting the server
```bash
# Transfer the server script (use base64 pattern if needed), then:
setsid /data/venvs/vllm-ds4/bin/python3 /tmp/qwen_image_server.py \
  </dev/null >/tmp/qwen_image_server.log 2>&1 &
```

### API
```
GET  /           → health
GET  /info      → model info + GPU memory
POST /generate  → generate image
```
Request:
```json
{
  "prompt": "A cyberpunk city at sunset",
  "negative_prompt": "blurry, low quality",
  "num_inference_steps": 50,
  "true_cfg_scale": 4.0,
  "height": 1024,
  "width": 1024,
  "seed": 42
}
```
Response: `{"image_base64": "...", "format": "png"}`

### Memory strategy
The 60-layer transformer is ~26GB in bfloat16 — doesn't fit on one RTX 5090 32GB. Use `enable_sequential_cpu_offload()`:
```python
pipe = DiffusionPipeline.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()
```
This moves layers CPU→GPU one at a time. Performance: ~100s for 512×512 @ 20 steps, ~400s for 1024×1024 @ 20 steps.

### `device_map` options (accelerate)
| Option | Supported | Result |
|--------|-----------|--------|
| `"auto"` | ❌ Not in this accelerate version | `NotImplementedError` |
| `"balanced"` | ✅ Yes | Distributes across 8 GPUs but slower due to NCCL attention communication |
| Sequential offload | ✅ Yes | **Fastest for this model** — transformer stays on GPU, only offloads when OOM |

### Known issues
- **OOM without offload:** Full pipeline on one GPU → `torch.OutOfMemoryError` (PyTorch reports 31.27 GiB used, nvidia-smi shows only ~15 MiB — PyTorch CUDA allocator fragmentation)
- **`true_cfg_scale` warning:** Logs `classifier-free guidance is not enabled since no negative_prompt is provided` — give a `negative_prompt` to silence
- **`tqdm` deprecation:** `set_progress_bar_config(enabled=False)` raises `TqdmKeyError`. Use `disable=True` instead
