# Wan2.2 T2V-A14B Text Encoder — UMT5 Loading Reference

## Verified Model Dimensions (from weight shapes, NOT config.json)

```
hidden_size          = 4096
d_kv                 = 512
d_ff                 = 10240       ← MUST set explicitly; default is 4x = 16384 (too large)
num_hidden_layers    = 24
num_attention_heads  = 8
relative_attention_num_buckets = 512
vocab_size           = 256384
```

config.json had WRONG values: `d_model=2560, intermediate_size=2727296, num_attention_heads=10, relative_attention_num_buckets=64`.

## SafeTensors Key Remapping

The safetensors use Wan-T5 internal naming, NOT HF UMT5EncoderModel naming. Keys must be remapped before `load_state_dict`.

### Remapping Rules

| SafeTensors Key Pattern | HF UMT5EncoderModel Key |
|---|---|
| `blocks.{N}.attn.q.weight` | `encoder.block.{N}.layer.0.SelfAttention.q.weight` |
| `blocks.{N}.attn.k.weight` | `encoder.block.{N}.layer.0.SelfAttention.k.weight` |
| `blocks.{N}.attn.v.weight` | `encoder.block.{N}.layer.0.SelfAttention.v.weight` |
| `blocks.{N}.attn.o.weight` | `encoder.block.{N}.layer.0.SelfAttention.o.weight` |
| `blocks.{N}.attn.q.bias` | `encoder.block.{N}.layer.0.SelfAttention.q.bias` |
| `blocks.{N}.attn.k.bias` | `encoder.block.{N}.layer.0.SelfAttention.k.bias` |
| `blocks.{N}.attn.v.bias` | `encoder.block.{N}.layer.0.SelfAttention.v.bias` |
| `blocks.{N}.attn.o.bias` | `encoder.block.{N}.layer.0.SelfAttention.o.bias` |
| `blocks.{N}.attn.norm1.weight` | `encoder.block.{N}.layer.0.layer_norm.weight` |
| `blocks.{N}.attn.norm1.bias` | `encoder.block.{N}.layer.0.layer_norm.bias` |
| `blocks.{N}.attn.norm2.weight` | `encoder.block.{N}.layer.0.final_layer_norm.weight` |
| `blocks.{N}.attn.norm2.bias` | `encoder.block.{N}.layer.0.final_layer_norm.bias` |
| `blocks.{N}.pos_embedding.embedding` | `encoder.relative_attention_bias.weight` |
| `blocks.{N}.ffn.gate.0.weight` | `encoder.block.{N}.layer.0.Wi_1.weight` |
| `blocks.{N}.ffn.gate.1.weight` | `encoder.block.{N}.layer.0.Wi_2.weight` |
| `blocks.{N}.ffn.wo.weight` | `encoder.block.{N}.layer.0.wo.weight` |

### Expected `load_state_dict` Outcome

```
missing: ~73 keys (LayerNorm bias keys — absent from safetensors, different norm scheme)
unexpected: 0
→ Expected and OK — use strict=False
```

## Session Log (2026-06-08)

Text encoder loaded in **43.7s** after applying key remapping (fp16 conversion model, non-diffusers format). No GPU required for text encoder loading.

The fp16 model at `/data/models/wan2.2_t2v_A14B/` uses `Umt5EncoderModel` with `model.safetensors` that has standard HF key names — **no remapping needed** for the fp16 model.

## Common Import Fixes

```python
# VAE import — WRONG paths (these fail in diffusers >= 0.38.0):
from diffusers.models.autoencoders.vae import AutoencoderKLWan   # wrong submodule
from diffusers.models.autoencoders.vae import AutoencoderKL       # wrong class for Wan VAE
from diffusers.models.autoencoders import AutoencoderKL           # wrong class for Wan VAE

# CORRECT:
from diffusers.models.autoencoders import AutoencoderKLWan        # ✓

# Text encoder — transformers.UMT5EncoderModel (not optimum):
from transformers import Umt5Config, Umt5EncoderModel             # ✓
```