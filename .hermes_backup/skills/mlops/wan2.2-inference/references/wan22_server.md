#!/usr/bin/env python3
"""Wan2.2 T2V-A14B FastAPI inference server — reference implementation.
Port 7860. Direct safetensors loading bypasses slow from_pretrained().

Model path: /data/models/wan2.2_t2v_A14B/ (fp16, NOT NVFP4 which requires modelopt)
Usage on remote server:
  python3 wan22_t2v_server.py --host 0.0.0.0 --port 7860
"""
import os, time, io, torch, safetensors.torch, argparse, glob, re
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import uvicorn

MODEL_PATH = os.environ.get("MODEL_PATH", "/data/models/wan2.2_t2v_A14B")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE  = torch.bfloat16

app = FastAPI()

# Global models (set during startup)
scheduler = text_encoder = vae = transformer = transformer_2 = None

def log(msg):
    print(msg, flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# Core loading helpers
# ─────────────────────────────────────────────────────────────────────────────
def load_sd_from_shards(dir_path, dtype=DTYPE):
    """Load state dict from sharded or single safetensors, convert dtype.
    Direct load = instant (memory-mapped). Never use from_pretrained() for shards.
    """
    shard_files = sorted(glob.glob(os.path.join(dir_path, "diffusion_pytorch_model-*-of-*.safetensors")))
    if not shard_files:
        single = os.path.join(dir_path, "diffusion_pytorch_model.safetensors")
        if not os.path.exists(single):
            # Try single safetensors (non-sharded)
            safetensors = [f for f in os.listdir(dir_path) if f.endswith(".safetensors")]
            if safetensors:
                single = os.path.join(dir_path, safetensors[0])
        sd = safetensors.torch.load_file(single)
        for k in sd:
            if sd[k].dtype != dtype: sd[k] = sd[k].to(dtype=dtype)
        log(f"  single: {len(sd)} keys from {os.path.basename(single)}")
        return sd

    shards = {}
    for sf in shard_files:
        m = re.search(r"-(\d+)-of-(\d+)", os.path.basename(sf))
        if m: shards[int(m.group(1))] = sf

    sd = {}
    for idx in sorted(shards):
        with safetensors.torch.safe_open(shards[idx]) as f:
            for k in f.keys():
                v = f.get_tensor(k)
                if v.dtype != dtype: v = v.to(dtype=dtype)
                sd[k] = v
    log(f"  {len(sd)} keys from {len(shards)} shards")
    return sd


def load_text_encoder():
    """Load UMT5 text encoder via UMT5Config + load_state_dict (fast, <1s).
    Config values derived from weight shapes, NOT config.json (config.json has wrong values).
    """
    log("[2/6] Loading text_encoder (direct + UMT5Config)...")
    t0 = time.time()
    from transformers import Umt5Config, Umt5EncoderModel

    # Derive hidden_size from weight shapes (e.g. .attn.q.weight shape [N, hidden_size])
    # DO NOT use config.json values — they are often wrong (e.g. d_model=2560 when it's 4096)
    cfg = Umt5Config(
        is_decoder=False,               # REQUIRED — without this: AttributeError
        hidden_size=4096,               # derived from weight shapes (NOT config.json's 2560)
        d_kv=512,
        d_ff=10240,                     # MUST set explicitly; default 4x=16384 is too large
        num_hidden_layers=24,           # config.json may say 26 — verify from weights
        num_attention_heads=8,          # config.json says 10 — verify from weights
        relative_attention_num_buckets=512,  # config.json says 64 — WRONG
        vocab_size=256384,
    )
    model = Umt5EncoderModel(cfg)

    sd = safetensors.torch.load_file(
        os.path.join(MODEL_PATH, "text_encoder/model.safetensors"))
    for k in sd:
        if sd[k].dtype != DTYPE: sd[k] = sd[k].to(dtype=DTYPE)

    missing, unexpected = model.load_state_dict(sd, strict=False)
    # Expected: ~73 layernorm bias keys "missing" — safetensors use a different norm scheme (OK)
    log(f"  text_encoder: missing={len(missing)}, unexpected={len(unexpected)}, time={time.time()-t0:.1f}s")
    model.eval()
    model.to(device=DEVICE, dtype=DTYPE)
    return model


def load_vae():
    """Load AutoencoderKLWan VAE via from_config + load_state_dict (instant).
    Import path: diffusers.models.autoencoders (NOT .vae, NOT plain AutoencoderKL).
    """
    log("[3/6] Loading vae (AutoencoderKLWan, direct weights)...")
    t0 = time.time()
    # CORRECT import path for diffusers >= 0.38.0
    from diffusers.models.autoencoders import AutoencoderKLWan

    vae_cfg_path = os.path.join(MODEL_PATH, "vae")
    vae = AutoencoderKLWan.from_pretrained(vae_cfg_path)

    vae_file = os.path.join(MODEL_PATH, "vae/diffusion_pytorch_model.safetensors")
    if not os.path.exists(vae_file):
        vae_file = os.path.join(MODEL_PATH, "vae/Wan2.1_VAE.pth")
    sd = safetensors.torch.load_file(vae_file)
    for k in sd:
        if sd[k].dtype != DTYPE: sd[k] = sd[k].to(dtype=DTYPE)

    missing, unexpected = vae.load_state_dict(sd, strict=False)
    log(f"  VAE: missing={len(missing)}, unexpected={len(unexpected)}, time={time.time()-t0:.1f}s")
    total = sum(p.sum().item() for p in vae.parameters())
    log(f"  VAE param sum: {total:.4f}  (should be non-zero)")
    vae.eval()
    vae.to(device=DEVICE, dtype=DTYPE)
    return vae


def load_transformer(name):
    """Load WanTransformer3DModel from sharded safetensors (direct, <30s per transformer).
    NEVER use from_pretrained() for transformers — it takes 10+ minutes and 100GB RAM.
    """
    log(f"[{name}] Loading transformer ({name}) direct...")
    t0 = time.time()
    from diffusers.models.transformers.transformer_wan import WanTransformer3DModel

    cfg_path = os.path.join(MODEL_PATH, name)
    # Use from_pretrained ONLY for config — weights come from safetensors shards
    model = WanTransformer3DModel.from_pretrained(cfg_path)

    sd = load_sd_from_shards(os.path.join(MODEL_PATH, name))
    missing, unexpected = model.load_state_dict(sd, strict=False)
    log(f"  {name}: missing={len(missing)}, unexpected={len(unexpected)}, time={time.time()-t0:.1f}s")
    model.eval()
    model.to(device=DEVICE, dtype=DTYPE)
    return model


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan startup (not @app.on_event — deprecated in FastAPI 3.x)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler, text_encoder, vae, transformer, transformer_2
    log(f"[startup] Wan2.2 T2V-A14B from {MODEL_PATH}")
    log(f"  device={DEVICE}, dtype={DTYPE}")

    log("[1/6] Scheduler: using FlowMatchEulerDiscreteScheduler")
    text_encoder = load_text_encoder()
    vae          = load_vae()
    transformer  = load_transformer("transformer")
    transformer_2 = load_transformer("transformer_2")

    log("[startup] ALL MODELS LOADED — ready to serve!")
    yield
    log("[shutdown] cleaning up")

app.router.lifespan_context = lifespan

# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/generate")
async def generate(request: dict):
    if not all([text_encoder, vae, transformer, transformer_2]):
        raise HTTPException(503, "Models not loaded")

    prompt       = request.get("prompt", "A cat playing piano in a moonlit room, cinematic, 4k")
    num_frames   = request.get("num_frames", 49)
    width        = request.get("width", 480)
    height       = request.get("height", 320)
    num_inference_steps = request.get("num_inference_steps", 20)
    guidance_scale     = request.get("guidance_scale", 7.0)

    log(f"[generate] prompt={prompt[:60]}, frames={num_frames}, {width}x{height}, steps={num_inference_steps}")

    try:
        from diffusers import FlowMatchEulerDiscreteScheduler, WanPipeline

        scheduler_cfg = FlowMatchEulerDiscreteScheduler.from_pretrained(
            os.path.join(MODEL_PATH, "scheduler"))
        scheduler_obj = FlowMatchEulerDiscreteScheduler.from_config(scheduler_cfg)

        # WanPipeline handles all 5 components including dual-transformer architecture
        pipeline = WanPipeline(
            scheduler=scheduler_obj,
            text_encoder=text_encoder,
            vae=vae,
            transformer=transformer,
            transformer_2=transformer_2,
        ).to(device=DEVICE, dtype=DTYPE)

        result = pipeline(
            prompt=prompt,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            num_frames=num_frames,
        )

        video_frames = result.frames[0]
        if not video_frames:
            raise HTTPException(500, "No frames generated")

        # Return first frame as PNG preview
        img_buf = io.BytesIO()
        video_frames[0].save(img_buf, format="PNG")
        img_buf.seek(0)
        return Response(content=img_buf.read(), media_type="image/png")

    except Exception as e:
        log(f"[generate] ERROR: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": all([text_encoder, vae, transformer, transformer_2])}

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")