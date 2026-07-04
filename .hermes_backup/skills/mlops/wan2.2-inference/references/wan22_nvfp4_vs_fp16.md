# Wan2.2 NVFP4 vs fp16 — Model Variant Decision Guide

## Two Available Model Variants on 10.10.70.88

| Property | NVFP4 (`*Diffusers-NVFP4`) | fp16 (`/data/models/wan2.2_t2v_A14B/`) |
|---|---|---|
| Location | `/data/models/wan2.2_t2v_A14B_diffusers_nvfp4/` | `/data/models/wan2.2_t2v_A14B/` |
| Size | 33GB | 132GB |
| Format | Diffusers (22 safetensors, sharded) | Non-diffusers (.pth + safetensors) |
| Weight dtype | Packed NF4 uint8 (4-bit) | fp16/bf16 |
| Loading | **Requires modelopt** | Direct safetensors load |
| GPU memory | Lower VRAM | Higher VRAM |

## NVFP4 — Why It Fails Without modelopt

Transformer safetensors contain **packed 4-bit NF4 weights** stored as uint8:
```
blocks.10.attn1.to_k.weight: dtype=uint8, shape=[5120, 2560]
  → represents a [5120, 5120] fp16 matrix (4-bit packing)
  → expected shape when loading: [5120, 5120]
  → got shape: [5120, 2560]  ← shape mismatch
```

Loading without dequantization: `ValueError: expected shape torch.Size([5120, 5120]), but got torch.Size([5120, 2560])`

**What exists in the venv but is insufficient:**
- `diffusers.quantizers.modelopt.NVIDIAModelOptQuantizer` — exists but requires modelopt core
- `compressed_tensors.NVFP4PackedCompressor` — exists but requires modelopt core to function
- `compressed_tensors` package — present, but CompressedTensoricConfig is missing

**modelopt is NOT on PyPI.** Install from NVIDIA NGC container or NVIDIA GitHub. Until then, NVFP4 cannot be loaded.

## fp16 Model — Structure

The original fp16 model at `/data/models/wan2.2_t2v_A14B/` uses `WanPipeline` (class_name in model_index.json):

| Component | Path | Format | Notes |
|---|---|---|---|
| text_encoder | `text_encoder/model.safetensors` | Umt5EncoderModel, hidden_size=2560, HF keys | No remapping needed |
| transformer | `high_noise_model/` | 6 safetensors shards | ~46GB |
| transformer_2 | `low_noise_model/` | 6 safetensors shards | ~56GB |
| vae | `vae/Wan2.1_VAE.pth` | .pth file | Load via safetensors or torch.load |
| scheduler | `scheduler/` | JSON config | Instant from config |

## Decision Rule

**Always use the fp16 model (`/data/models/wan2.2_t2v_A14B/`)** for new deployments:
- No modelopt dependency
- Direct safetensors loading (fast, memory-mapped)
- WanPipeline.from_pretrained() compatible with class_name="WanPipeline"

Use NVFP4 only when VRAM is critically constrained and modelopt is installed.