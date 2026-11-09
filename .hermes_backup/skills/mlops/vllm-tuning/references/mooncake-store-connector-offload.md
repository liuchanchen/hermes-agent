# MooncakeStoreConnector KV Offload (vLLM 0.25.0)

Verified 2026-08-18 against `vllm/vllm-openai:v0.25.0-flashinfer0614-local` (present on 70.88 + 70.92), which bundles `mooncake-transfer-engine 0.3.10.post2`.

## What it is
3-tier *reusable prefix* KV cache: GPU HBM (L1, vLLM BlockPool) → Mooncake Store DRAM (L2) → NVMe SSD (L3).
It is NOT a transparent swap of active decode working-set KV (that stays vLLM scheduler/preemption territory).
Two INDEPENDENT eviction paths: vLLM evicts L1 blocks; Mooncake Master evicts L2→L3 (`offload_on_evict`) and optionally promotes L3→L2 (`promotion_on_hit`).

## Verified from in-image source
- Connector registered as **`MooncakeStoreConnector`** in `vllm/distributed/kv_transfer/kv_connector/factory.py` → `vllm.distributed.kv_transfer.kv_connector.v1.mooncake.store.connector`.
- vLLM store config = `MooncakeStoreConfig` (`store/worker.py`): fields `mode | metadata_server | master_server_address | global_segment_size | local_buffer_size | protocol | device_name | enable_offload`, loaded from **`$MOONCAKE_CONFIG_PATH`** (a JSON file).
- **`standalone-store` mode REQUIRES `global_segment_size == 0`** (rank contributes nothing; an external `mooncake_client` owns the DRAM pool + SSD tier).
- `--kv-transfer-config` takes the whole `KVTransferConfig` as **ONE JSON blob** (`json.loads` in arg_utils). Connector tuning lives under `"kv_connector_extra_config": {"load_async": true (default), "promotion_on_hit": ...}`. `kv_role` ∈ `kv_producer | kv_consumer | kv_both`.
- `MooncakeStoreConfig` (in-image) hard-asserts `standalone-store → global_segment_size == 0`, and logs a warning if standalone-store runs without `enable_offload`.

## The image bundles the store binaries — no separate mooncake image needed
`/usr/local/bin/mooncake_master` + `mooncake_client` ship INSIDE the vllm image. Run the standalone store as a keep-alive container from the same image.
- `mooncake_master` uses **gflags syntax** (`-flag=value`): `-rpc_port`, `-enable_offload`, `-offload_on_evict`, `-promotion_on_hit`, `-promotion_admission_threshold`, `-eviction_high_watermark_ratio` (default 0.90), `-eviction_ratio` (0.05), `-enable_disk_eviction`.
- `mooncake_client`: `-port` (default 50052), `-host`, `-global_segment_size` (default "4 GB"), `-enable_offload`, `-protocol` (tcp|rdma), `-metadata_server`, `-device_names`, `-start_offload_rpc_server`.
- Client SSD env vars: `MOONCAKE_OFFLOAD_FILE_STORAGE_PATH`, `MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES`, `MOONCAKE_BUCKET_EVICTION_POLICY=lru`, `MOONCAKE_USE_URING`, `MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES`.

## Working reference config (eager + promotion)
```bash
# master (gflags)
mooncake_master -rpc_port=50051 -enable_offload=true -offload_on_evict=true \
  -promotion_on_hit=true -promotion_admission_threshold=2 \
  -eviction_high_watermark_ratio=0.90 -eviction_ratio=0.05 -enable_disk_eviction=true
# client
mooncake_client -master_server_address=127.0.0.1:50051 -host=0.0.0.0 -port=50053 \
  -global_segment_size="128GB" -enable_offload=true -protocol=tcp -start_offload_rpc_server=true
```
vLLM `$MOONCAKE_CONFIG_PATH` JSON:
```json
{"mode":"standalone-store","metadata_server":"P2PHANDSHAKE",
 "master_server_address":"127.0.0.1:50051","global_segment_size":0,
 "local_buffer_size":"4GB","protocol":"tcp","device_name":"","enable_offload":true}
```
`--kv-transfer-config` JSON: `{"kv_connector":"MooncakeStoreConnector","kv_role":"kv_both","kv_parallel_size":1,"kv_buffer_size":1000000000,"kv_connector_extra_config":{"load_async":true,"promotion_on_hit":true}}`

## Validation pattern (do BEFORE a real GPU deploy)
Write a small python validator locally, push via base64 stdin (`ssh host 'base64 -d > /tmp/x.py'`), run in-container:
`docker run --rm -v /tmp/x.py:/tmp/x.py --entrypoint bash IMAGE -lc 'python3 /tmp/x.py'`.
Assert `MooncakeStoreConfig.load_from_config()` parses and `KVTransferConfig(**dict)` round-trips.
**NOTE:** `KVTransferConfig` has NO `from_cli`/`from_dict` — construct the dataclass directly from the dict to validate.

## Script
`/home/jianliu/work/tgu01-pro-model-deployment/mooncake_kv_offload/enable_mooncake_kv_offload.sh` — launches store container + vLLM with the connector; knobs at top (MODEL_PATH, TP_SIZE, PROTOCOL, DEVICE_NAME for rdma).

## Pitfalls
- `chatgpt.com/c/...` links are login-gated (HTTP 403) — agent cannot read them. Get the mechanism from the user's pasted doc + in-image source instead (they matched).
- `mooncake_client --help` without GPUs fails `cannot open shared object libcuda.so.1` — inspect flags under `--gpus all`.
- Flag-inspection greps must use `grep -E` / pattern without leading `-`, or grep treats `-port` as an option.
