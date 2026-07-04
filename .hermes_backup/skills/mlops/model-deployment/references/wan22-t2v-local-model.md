# Wan 2.2 T2V Local Model Format — Deployment Reference

## Model Path
`/data/models/wan2.2_t2v_A14B/` on 70.88

## Model Format (NOT Standard Diffusers)

The model is **NOT** in HuggingFace diffusers format. It has 6 components:

| Component | Type | Notes |
|-----------|------|-------|
| `high_noise_model/` | diffusers safetensors + config | MoE expert router + expert weights |
| `low_noise_model/` | diffusers safetensors + config | Second MoE expert set |
| `models_t5_umt5-xxl-enc-bf16.pth` | `torch.save()` archive | 5-tuple persistent ID format |
| `Wan2.1_VAE.pth` | `torch.save()` archive | Same 5-tuple persistent ID format |
| `google/umt5-xxl/tokenizer/` | HuggingFace tokenizer | Standard |
| `*.json` config files | Model config | At model root |

### 5-Tuple Persistent ID Format (PyTorch 2.11 Blocker)

The T5 and VAE `.pth` files are saved via `torch.save()` with persistent ID tuples:
```python
('storage', storage_cls, key, device, size)
# e.g.:
('storage', <class 'torch.storage.TypedStorage'>, 'weight', 'meta', torch.Size([512, 512]))
```

**The problem in PyTorch 2.11+**: `_rebuild_tensor` now does:
```python
def _rebuild_tensor(storage, storage_offset, size, stride):
    t = torch.empty((0,), dtype=storage.dtype, device=storage._untyped_storage.device)
    return t.set_(storage._untyped_storage, storage_offset, size, stride)
```
It accesses `storage.dtype` and `storage._untyped_storage.device` — the persistent ID tuple has neither.

## Server Pattern (Same as Qwen-Image-2512)

**vLLM cannot serve diffusion models.** Correct stack:
```
diffusers Pipeline + FastAPI + uvicorn
```

GPU offloading: `sequential` CPU offload is ~3× faster than `device_map="balanced"`.

## Fixing Persistent_load for PyTorch 2.11+

The fix is to return an object with both `.dtype` AND `._untyped_storage` from `persistent_load`.

### Option A — TypedStorage from raw bytes (recommended)
```python
def persistent_load(pid):
    if pid[0] == 'storage':
        name, cls, key, device, size = pid
        dtype = torch.float32  # detect from cls or model config
        storage = torch.frombuffer(torch.empty(size, dtype=dtype).cpu().numpy().tobytes(),
                                    dtype=dtype).clone().storage()
        # Wrap so .dtype and ._untyped_storage are available
        return TypedStorageWrapper(storage, dtype)
    return pid
```

### Option B — Wrapper class
```python
class StorageWrapper:
    def __init__(self, storage, dtype):
        self._storage = storage
        self.dtype = dtype
    @property
    def _untyped_storage(self):
        return self._storage._untyped_storage
```

### Option C — Patch `_rebuild_tensor` directly
In `torch/_utils.py`, modify `_rebuild_tensor` to handle plain Tensor storages:
```python
def _rebuild_tensor(storage, storage_offset, size, stride):
    if isinstance(storage, torch.Tensor):
        return storage.storage()
    # falls back to original TypedStorage path
```

### Option D — Use `pickletools` to bypass persistent_load entirely
Scan pickle opcodes and replace persistent ID references with pre-loaded storage tensors.

## Key Files on 70.88

- `/tmp/wan22_t2v_server.py` — FastAPI server (written in session)
- `/tmp/setup_wan22_local.py` — Conversion script (written in session, needs fix)
- `/tmp/test_t5_load.py` — T5 load test (written in session)
- `/tmp/wan22_t2v_server.log` — Server log

## Port
Server runs on port **8001**.

## Status
**BLOCKED** — persistent ID format fix not yet completed. Conversion script at `/tmp/setup_wan22_local.py` needs the TypedStorage wrapper approach.