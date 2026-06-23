# wan2.2 SGLang generate.log — CUDA OOM on RTX 5090 32GB
# 2026-06-09 13:32, 70.88, SGLang + wan2.2_T2V_A14B_Diffusers_NVFP4

## Root cause
```
torch.OutOfMemoryError: CUDA out of memory.
GPU 0 has a total capacity of 31.36 GiB of which 8.88 MiB is free.
Process has 29.55 GiB memory in use. Tried to allocate 34.00 MiB.
```

## Fatal error sequence
1. Model loads into GPU (~29.6 GiB)
2. `torch.OutOfMemoryError` at `fsdp_load.py:load_model_from_full_model_state_dict`
3. SGLang falls back: "Error while loading customized transformer, falling back to native version"
4. Fallback also OOMs → "Error while loading component: transformer"
5. Worker 0 shuts down
6. "Rank 0 scheduler is dead"
7. Parent process receives EOFError on `multiprocessing.connection.recv`

## Model components (from log)
- `WanPipeline` (diffusers 0.36.0)
- `transformer` — OOM here (9.3 GB shard 1)
- `transformer_2` — MoE expert (same size)
- `vae` — 243 MB
- `text_encoder` — UMT5EncoderModel (9.3 + 1.4 GB)
- `tokenizer` — T5TokenizerFast

## What works
- SGLang server startup and scheduler binding work fine
- Model loading up to the point of full transformer placement fails
- The `generate` CLI launches a local server via `launch_server()`, which crashes
- BF16 inference runs (376K MP4 files produced via SGLang)
- Native HF Diffusers generate works (71K MP4, smaller output)

## Key log lines
```
[06-09 13:32:27] Error while loading customized transformer, falling back to native version
[06-09 13:32:27] Error while loading component: transformer, component_model_path='.../transformer'
[06-09 13:32:32] Worker 0: Shutdown complete.
[06-09 13:32:34] Rank 0 scheduler is dead. Please check if there are relevant logs.
[06-09 13:32:35] Exit code: 1
```

## Mitigation options
1. `--dit-cpu-offload` — offload transformer layers during inference
2. `--vae-cpu-offload` — move VAE off GPU during denoising
3. `--text-encoder-cpu-offload` — move text encoder off GPU
4. `--mem-fraction-static 0.88` — limit PyTorch memory fraction (already set in test)
5. Use BF16 precision instead of FP32
6. Use sequence parallel (SP) or Ulysses parallel to shard activations