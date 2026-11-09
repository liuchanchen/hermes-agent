# MooncakeStoreConnector KV Offload (vLLM 0.25.0)

Verified 2026-08-18 against `vllm/vllm-openai:v0.25.0-flashinfer0614-local` (on 70.88, migrated from 70.92). This image bundles **mooncake-transfer-engine 0.3.10.post2** with `mooncake_master` + `mooncake_client` binaries at `/usr/local/bin/` (package under `/usr/local/lib/python3.12/dist-packages/mooncake/`) — no separate `kvcache-ai/mooncake` image needed for the standalone store.

## Architecture (3-tier KV cache)

L1 GPU HBM (vLLM BlockPool) ↔ L2 Mooncake Store DRAM ↔ L3 NVMe SSD.

Two INDEPENDENT eviction systems:
- vLLM BlockPool evicts GPU KV blocks (L1).
- Mooncake Master/Store evicts DRAM → SSD (L2 → L3, via `-offload_on_evict`).

On a later prefix hit, vLLM allocates GPU blocks and loads KV back from DRAM or SSD (DirectIO staging buffer), skipping the matched prefill. This extends **reusable prefix KV cache** capacity — it is NOT a transparent swap of active decode working-set KV (that stays vLLM scheduler/preemption territory).

## vLLM-side wiring (verified from source)

- Connector name: `MooncakeStoreConnector` (registered in `vllm/distributed/kv_transfer/kv_connector/factory.py`).
- Passed via `--kv-transfer-config '<JSON blob>'` (`arg_utils.py`: `--kv-transfer-config` is `json.loads` typed, whole dataclass in one JSON). Example:
  ```json
  {"kv_connector":"MooncakeStoreConnector","kv_role":"kv_both","kv_parallel_size":1,
   "kv_buffer_size":1000000000,"kv_connector_extra_config":{"load_async":true}}
  ```
- The store config JSON is read by vLLM from env **`MOONCAKE_CONFIG_PATH`** (`MooncakeStoreConfig.load_from_config()` in `vllm/.../mooncake/store/worker.py`).
- Store config schema (`MooncakeStoreConfig` dataclass): `mode`, `metadata_server`, `master_server_address`, `protocol`, `device_name`, `global_segment_size`, `local_buffer_size`, `enable_offload`.
  - `standalone-store` mode **REQUIRES `global_segment_size == 0`** (rank contributes nothing; external mooncake_client owns DRAM pool + SSD tier).
  - `metadata_server: "P2PHANDSHAKE"` is valid (transfer-engine mode using the peer handshake instead of a separate metadata store).
  - `local_buffer_size` accepts unit strings ("4GB" → 4294967296 bytes).
- Connector scheduler reads `load_async` (default true) and `cache_prefix` from `kv_connector_extra_config`.

## mooncake_master gflags (gflags syntax: `-flag=value`)

Supported in this build: `-rpc_port`, `-enable_offload` (default **false** — must set true), `-offload_on_evict`, `-offload_force_evict`, `-enable_disk_eviction`, `-eviction_high_watermark_ratio` (default 0.90), `-eviction_ratio` (default 0.05), `-allow_evict_soft_pinned_objects`, `-memory_allocator`, `-allocation_strategy`, HA flags.

## mooncake_client gflags

`-port` (50052), `-host`, `-global_segment_size` ("4 GB" default), `-enable_offload` (default **false**), `-protocol` (tcp), `-metadata_server` (http://127.0.0.1:8080/metadata), `-device_names`, `-start_offload_rpc_server`. **Needs libcuda** — run with `--gpus all` (plain `--help` fails with `libcuda.so.1` error). Offload env vars: `MOONCAKE_OFFLOAD_FILE_STORAGE_PATH`, `MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES`, `MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES`, `MOONCAKE_BUCKET_EVICTION_POLICY=lru`, `MOONCAKE_USE_URING`.

## ⚠️ promotion_on_hit NOT supported in this image (verified, don't pass it)

- `grep -rn "promotion_on_hit"` across the whole vLLM package → **0 hits**; the connector only reads `load_async` / `cache_prefix`.
- `mooncake_master --help` full gflag list → **no promotion flag**.
- Binary `strings` show "Proceeding with promotion" / "Cannot promote" but those are **HA standby promotion** strings (master failover states PROMOTING/PROMOTED/FAILED), NOT SSD→DRAM KV promotion.
- `-promotion_on_hit` / `-promotion_admission_threshold` are newer Mooncake features; gflags **rejects unknown flags**, so passing them here fails. Only eviction flags are usable in 0.3.10.post2.

## Validation technique (verify configs parse inside the container before deploying)

```bash
# store config: run inside the image, MOONCAKE_CONFIG_PATH must point at the JSON
MOONCAKE_CONFIG_PATH=/tmp/mc.json python3 -c \
 "from vllm.distributed.kv_transfer.kv_connector.v1.mooncake.store.worker import MooncakeStoreConfig as C; c=C.load_from_config(); print(c); assert c.mode=='standalone-store' and c.global_segment_size==0 and c.enable_offload"
# kv-transfer-config: KVTransferConfig has NO from_cli/from_dict; build the dataclass directly: KVTransferConfig(**json.loads(blob))
```
Push test scripts to the host via base64 (`base64 -d > file`) — SSH heredoc quoting is fragile for JSON-with-quotes payloads.

## Deployment script

`/home/jianliu/work/tgu01-pro-model-deployment/mooncake_kv_offload/enable_mooncake_kv_offload.sh` — deploys: (1) SSD pool dir, (2) store config JSON (standalone-store), (3) store container running `mooncake_master` + `mooncake_client` from the vLLM image, (4) vLLM container with `--kv-transfer-config`. Adjust `MODEL_PATH`/`TP_SIZE`/`PORT`; `PROTOCOL=rdma DEVICE_NAME=mlx5_0` for RoCE. NOTE: the copy on 88 is the OLD version still containing `-promotion_on_hit`; the local copy is corrected (user declined re-sync).

## Exact launch order (start action, verified 2026-08-24 from the 617-line script)

Hard dependency chain — each step BLOCKS on the previous one (STARTUP_TIMEOUT 1800s), and any failure triggers `cleanup_failed_start` (removes all 3 containers):

0. `validate_config` — check docker/curl/nvidia-smi/rg, model config.json+safetensors, image, driver; validate numeric params; mkdir pool/hf-cache/log/runtime; build RDMA args; deep image validation (MooncakeStoreConnector present + mooncake_master flags).
1. `write_config` (start only) — emit `mooncake-store.json` (client) + `mooncake-master.yaml` (master); throwaway container asserts `MooncakeStoreConfig.load_from_config()` parses.
2. `remove_managed_containers` + port-conflict check (PORT, MASTER_PORT, CLIENT_PORT, CLIENT_HTTP_PORT; reject overlap with Mooncake RPC range).
3. Start **master** (`--entrypoint mooncake_master`), wait TCP on MASTER_PORT (50051), `verify_master_offload_config` greps startup line for `enable_offload=1` + matching `offload_on_evict`.
4. Start **client** (`--entrypoint mooncake_client`, `--master_server_address`, `--global_segment_size`, `--start_offload_rpc_server`, `--enable_http_server`), wait HTTP `/health` on CLIENT_HTTP_PORT (9300), verify log lacks `Bucket backend max_total_size not set` (unbounded SSD run refused).
5. Build `kv_transfer_config` JSON: `{"kv_connector":"MooncakeStoreConnector","kv_role":"kv_both","kv_load_failure_policy":...,"kv_connector_extra_config":{"load_async":true,"cache_prefix":...,"preferred_segment":"<CLIENT_HOST>:<CLIENT_PORT>"}}`.
6. Start **vLLM** last (`--kv-transfer-config "$kv_transfer_config"`, mounts store config, `VLLM_MOONCAKE_STORE_TIER_LOG`), wait `/v1/models` returns served-model-name.

`baseline` action = same vLLM server WITHOUT master/client/--kv-transfer-config (APC-only control).
`OFFLOAD_ON_EVICT` semantics: true -> cold DRAM objects persisted to SSD only when DRAM crosses the high-watermark (Mooncake 0.3.10 has NO promotion_on_hit; SSD hits load straight back into GPU blocks).

Mooncake needs stable registered KV addresses: clear `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` ONLY for Mooncake runs (baseline keeps it).

## Source references

- vLLM docs: MooncakeStoreConnector usage guide (https://docs.vllm.ai/en/stable/features/mooncake_store_connector_usage/)
- kvcache-ai/Mooncake: mooncake-store-deployment-guide.md (https://github.com/kvcache-ai/Mooncake)
- vLLM source: `vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/{worker,scheduler,connector}.py`

Note: `chatgpt.com/c/<id>` deep links are login-gated — curl returns HTTP 403; rely on pasted doc content / source instead.
