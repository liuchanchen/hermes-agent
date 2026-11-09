---
name: pd-disaggregation
description: Use when running or debugging vLLM PD disaggregation.
version: 0.1.0
author: Hermes Agent
platforms: [linux]
metadata:
  hermes:
    tags: [vLLM, Mooncake, PD, RDMA, RoCE, KV-transfer, Benchmark, WarpDrive]
---

# PD Disaggregation (vLLM + Mooncake) — Class Playbook

Prefill/decode (PD) disaggregation with vLLM's MooncakeConnector + mooncake-transfer-engine over RoCE RDMA. Covers bring-up, smoke tests, benchmark flows, and failure triage. Host-specific values (RDMA device name, cluster IP, staged runtimes, script paths, experiment history) live in the host skills (`remote-server-70-106`, `remote-server-70-96`). This skill holds everything generic.

## Architecture

Three containers + one bootstrap port, all `--network host`:

| Container | Port | Role | GPUs |
|---|---|---|---|
| prefill (P) | 8100 | kv_producer, TP=4 (GPUs 0-3) | prefill, ships KV via RDMA |
| decode (D) | 8200 | kv_consumer, TP=4 (GPUs 4-7) | pulls KV, decodes |
| proxy | 8000 | routes chat requests to P/D | — |
| bootstrap | 8998 | mooncake handshake | — |

Requests hit the proxy :8000 ONLY. `/health` and `/v1/models` on the proxy 404 **by design** — probe P/D directly on 8100/8200 for those. Requests must use the served model name `DeepSeek-V4-Flash`; the raw model path 404s on decode.

## Bring-up recipe (every item required)

1. **`--device /dev/infiniband/uverbs0 --device /dev/infiniband/uverbs1 --device /dev/infiniband/rdma_cm`** on P/D — docker passes /sys/class/infiniband but NOT /dev/infiniband → engine sees 0 HCAs without it.
2. **`-e WITH_NVIDIA_PEERMEM=0`** on P/D — see next section; the most common killer.
3. kv_connector_extra_config: `{"mooncake_protocol":"rdma","device_name":"<host RDMA device>","num_workers":10}` — protocol default "tcp" also breaks; device name is HOST-specific (106: `mlx5_bond_0`, 96: `mlx5_1`).
4. kv_role: `kv_producer` / `kv_consumer` (kv_ prefix required by the image).
5. `--enable-cumem-allocator` on P/D (expandable_segments conflicts with the connector).
6. Unset http_proxy/https_proxy in EVERY container (image bakes an unreachable proxy; aiohttp/httpx trust_env then hangs/fails on localhost calls).
7. Bootstrap connector patch bind-mounted over the in-image mooncake_connector.py (retries transient bootstrap errors instead of killing the engine) — lives in the deployment dir `mooncake_patch/`.
8. mooncake runtime mounted at a fixed path + LD_LIBRARY_PATH — see staging below.

Backslash-continued `docker run` blocks: **a blank line inside the block silently truncates the command** → `docker run requires at least 1 argument`. `bash -n` does NOT catch it — eyeball the continuation block for blank lines.

## The #1 failure: GPU memory registration (WITH_NVIDIA_PEERMEM)

Signature (prefill.log, on every KV send):

```
rdma_transport.cpp:545 Memory region not registered by any active device(s)
Sending to <ip>:<port> failed (ret=-1) after ~2.5ms (N descriptors, 5MB)
```

→ 0/N transfers → decode EngineDeadError → clean exit. Cause: by default mooncake registers GPU KV buffers with `ibv_reg_mr()`, which requires the `nvidia_peermem` kernel module — NOT loaded on the cluster hosts (`lsmod | grep peermem` empty on both 106 and 96). Fix: `-e WITH_NVIDIA_PEERMEM=0` selects the DMA-BUF registration path, no module needed. After the fix: 8/8 transfers @ 1689 MB/s (96) and a clean 9-run matrix.

Triage note: this failure is **independent of the mooncake runtime version** — 0.3.10.post2 and 0.3.11 failed byte-identically (A/B-tested 2026-09-04). Do not burn time swapping runtime versions when you see the MR signature; check peermem first.

## Runtime staging without root

No sudo on cluster hosts → runtimes are extracted wheels under `~/mooncake-runtime-<ver>/`, mounted `-v ~/mooncake-runtime-<ver>:/opt/mooncake-runtime:ro` with `-e LD_LIBRARY_PATH=/opt/mooncake-runtime:/opt/mooncake-runtime/.libs` (and the mooncake python package made importable as the deployment scripts do).

- Get a wheel: `pip download mooncake-transfer-engine==0.3.11 --no-deps -d /tmp/mk` (on a host with pypi), then unzip into the runtime dir.
- **Hashed-libs trap**: the 0.3.10 wheel ships `.so` files referencing hash-suffixed libs (`libglog-c040a6f3.so.0.4.0`, `libunwind-5d1f6f10.so.8.0.1`, `libjsoncpp-7d699962.so.1.9.5`, libcudart) but bundles no `.libs/`. Source them from a wheel that bundles them (0.3.11's `.libs/`) with **`cp -L` (real files)** — plain symlinks carry absolute host paths that don't exist inside the container (different mount point) and dlopen fails anyway.
- Verify BEFORE a full launch (~30s): import + engine init inside the serving image, e.g.
  `docker run --rm --gpus all --network host -v <runtime>:/opt/mooncake-runtime:ro -e LD_LIBRARY_PATH=... <image> python -c "from mooncake import engine; e=engine.TransferEngine(); print(e.initialize('0.0.0.0:12345','test','rdma','rdma'))"` — expect ret=0.

## Triage playbook (ordered)

| Symptom | First check | Fix |
|---|---|---|
| engine init sees 0 HCAs | /dev/infiniband inside container | `--device /dev/infiniband/*` (item 1) |
| MR-not-registered on send | `lsmod \| grep peermem` on host | `WITH_NVIDIA_PEERMEM=0` |
| `docker run requires at least 1 argument` | blank line in continuation block | remove blank lines |
| bootstrap errors kill engine at startup | in-image connector | bind-mount patched connector |
| localhost calls hang in container | baked http_proxy env | unset proxies in every container |
| proxy 404 on POST | model name | served name `DeepSeek-V4-Flash` |
| `cuMemExportToShareableHandle failed: 1` | fell back to MNNVL transport | recipe items 1-4 (RDMA protocol + device) |

## Smoke test procedure (before any benchmark)

1. Launch the stack; wait for `200` on P :8100/health and D :8200/health (curl --noproxy).
2. Write request JSON to a file on the host (`/tmp/req.json`) — nested quotes in `curl -d '{...}'` over ssh break silently (empty responses). Use `curl -d @/tmp/req.json`.
3. Send 3 known-answer prompts through :8000 (e.g. "2+3"→"5", capital of France→"Paris", count 1-5→"1 2 3 4 5"). Check `choices[0].message.content`, not HTTP code alone.
4. Grep prefill.log for `KV Transfer metrics:` — expect `Num successful transfers>0`, `Num failed transfers=0`, sane MB/s (RoCE 100G serving-path: ~1.5-1.7 GB/s observed — NOT a NIC limit; the raw engine does 9.5-11.9 GB/s on the same link, see the KV bandwidth section below).
5. Teardown via the stop script; confirm all GPUs back to baseline (~14 MiB) and no pd-disagg containers remain.

## Benchmark flow

`run_pd_test_flow.sh` (deployment dir, env-overridable): Phase 1 baseline (TP=8 co-located) → Phase 2 PD (proxy) → Phase 3 summary. 3 scenarios (2k/512@C8, 2k/512@C64, 16k/512@C64) × RUNS_PER_POINT (3), warmup per point, fixed seed, medians reported. Results: `results/<ts>/summary.csv` + per-run vllm bench JSON under `pd/<scen>_c<conc>/runN/`.

- `--check` = preflight only; `--execute` = run. Knobs: RESULT_DIR, IMAGE, RUNS_PER_POINT, BASELINE_LAUNCH, PD_LAUNCH, PD_HOST_IP...
- **PD-only variant** (baseline already collected): copy the script to `.pdonly` and python-replace the `# ---- Phase 1: BASELINE ... # ---- Phase 2` block with a comment; `bash -n` it; run with a fresh RESULT_DIR. Used for the 2026-09-04 96 PD matrix.
- Known gap: `collect_pd_metrics` regex doesn't match this vLLM build's metric lines → `pd_metrics.csv` columns come out empty; raw stats live in `logs/prefill.log` (`KV Transfer metrics:` line). Cosmetic.
- Cold-run trap: run 1 of each point is a JIT-cold outlier (TTFT ~40s at 16K); medians absorb it — never compare run-1s across arms.
- Single-node PD verdict (2026-09-04, 96): net loss — TTFT +27-38%, throughput −13-20%, TPOT unchanged. PD only pays off multi-node (96+98 DS-V4-Pro PP=2 per the Notion plan).

## KV bandwidth: real PD vs raw engine (2026-09-05, 96)

| Path | Bandwidth | % of 100G line (12.5 GB/s) |
|---|---|---|
| Real PD (MooncakeConnector per-KV-transfer, serving) | 1.55–1.65 GB/s | 12–13% |
| Raw mooncake engine, standalone bench, GPU→GPU loopback | write 9.5–9.8 / read 11.9 GB/s | 76–95% |

The 1.6 GB/s serving number is NOT a NIC limit: it is dominated by serving-path
overhead — small fragmented per-request sends, ~4 ms fixed per-transfer cost (alone
caps a 7 MB send at ~1.7 GB/s), TP/NCCL contention, same-host loopback. Consequences:
transfer ≈ 8% of the PD-vs-baseline TTFT delta at 16K; TPOT unchanged across all PD
points ⇒ the wire is never the single-node PD bottleneck; multi-node (96+98) has ~8×
bandwidth headroom on the current NIC. Before blaming hardware or tuning connector
knobs blindly, run the raw bench to locate the gap — recipe + full gotcha list in
`references/mooncake-raw-kv-bench-2026-09-05.md`.

Notion results write-up style (user preference): simple words, accuracy; result +
summary + key analysis only (applied 2026-09-05 to the PD page).

## References

- `references/70-96-experiment-2026-09-04.md` — full 68.96 session record: bug signatures, runtime A/B, smoke + matrix numbers, file locations.
- `references/mooncake-raw-kv-bench-2026-09-05.md` — standalone no-model mooncake KV bench: results, design, debugging saga (torch-allocator EFAULT, phantom batch_register success, dynamic RPC port).
