# Wan2.2-T2V-A14B SGLang Generate Log Analysis

## Source
`/home/jianliu/work/bench_test/wan_2_2_nvfp4/out_wan22_generate/generate.log`
Copied to local: `/home/jianliu/generate.log`

## What happened

SGLang Wan2.2 server (`generate.py`) launched with `performance_mode=speed` on a single RTX 5090 32GB.
Server initialized successfully (WanPipeline loaded, scheduler bind confirmed), then crashed during request dispatch.

## Key log lines

```
[06-09 13:32:13] Applying performance_mode=speed
[06-09 13:32:21] Scheduler bind at endpoint: tcp://127.0.0.1:5566
[06-09 13:32:22] Model already exists locally and is complete
[06-09 13:32:22] Using pipeline from model_index.json: WanPipeline
[06-09 13:32:22] Loading pipeline modules from config: {...}
[06-09 13:32:22] MoE pipeline detected. Adding transformer_2 to self.required_config_modules...
[06-09 13:32:22] Setting boundary ratio to 0.875
```

## Root cause: CUDA OOM

```
Traceback (most recent call last):
  File ".../fsdp_load.py", line 478, in load_model_from_full_model_state_dict
    sharded_tensor = torch.empty_like(...)
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 34.00 MiB.
GPU 0 has a total capacity of 31.36 GiB of which 8.88 MiB is free.
Process 2690081 has 1.77 GiB memory in use.
Including non-PyTorch memory, this process has 29.55 GiB memory in use.
Of the allocated memory 24.19 GiB is allocated by PyTorch, and 90.74 MiB is
reserved by PyTorch but unallocated.
```

Recovery attempt failed:
```
[06-09 13:32:27] Error while loading customized transformer, falling back to native version
[06-09 13:32:27] Error while loading component: transformer,
  component_model_path='/data/models/wan2.2_t2v_A14B_diffusers_nvfp4/transformer'
[06-09 13:32:32] Worker 0: Shutdown complete.
```

Server continued but scheduler died:
```
[06-09 13:32:34] Rank 0 scheduler is dead. Please check if there are relevant logs.
[06-09 13:32:35] Exit code: 1
```

## Diagnosis

RTX 5090 32GB is too small for Wan2.2-T2V-A14B at full precision with `performance_mode=speed`.
The `performance_mode=speed` maximizes GPU memory utilization for throughput, leaving no headroom.
29.55 GiB / 31.36 GiB already consumed at load time — only 8.88 MiB free.

## Mitigations to try

1. `--vae-cpu-offload` — move VAE off GPU during denoising
2. `--text-encoder-cpu-offload` — offload text encoder
3. `--dit-cpu-offload` or `--dit-layerwise-offload` — offload diffusion transformer layers
4. Reduce latent resolution in generation call
5. Lower `performance_mode` or remove it entirely
6. Use `--mem-fraction-static 0.80` or lower to cap memory usage

## Test script

User has a backend comparison test script:
```
/home/jianliu/work/bench_test/wan_2_2_nvfp4/out_wan22_generate/test_wan22_nvfp4_backends.sh
```
(11,439 bytes, copied from local `C:\Users\liuch\Downloads\`)