# Raw Mooncake KV-Transfer Bench — 2026-09-05 (70.96)

No vLLM, no model: two mooncake engines in containers, one holds + registers buffers
(serve role), one drives `batch_transfer_async_write` (bench role). Purpose: separate
transport capability from serving-path overhead, so bandwidth questions get answered
with a controlled number instead of inference from serving logs.

## Headline numbers (single ConnectX-6 Dx 100G RoCE, same-host GPU0→GPU1 loopback)

| Config | Write | Read |
|---|---|---|
| 1×8 MB × 20 iters | 3.87 GB/s (iter 1 = 17 ms handshake warmup) | 6.78 GB/s |
| 8×8 MB batch × 30 iters | 9.83 GB/s (79% of 12.5 GB/s line) | 11.88 GB/s (95%) |
| 16×8 MB batch × 30 iters | 9.54 GB/s (76%) | 11.90 GB/s (95%) |

Steady state ≈ 0.086 ms/MB + small fixed cost. Compare real PD serving (MooncakeConnector):
1.55–1.65 GB/s = 12–13% of line (2K: 7.4 MB in 4.5 ms; 16K: 80.7 MB in 52 ms; 236 transfers,
0 failures during the 16K matrix). The gap is the serving path, not the NIC: small
fragmented per-request sends, ~4 ms fixed cost per transfer (alone caps a 7 MB send at
~1.7 GB/s), TP/NCCL contention, same-host loopback (NIC→switch→same port).

## Design (mirrors vLLM MooncakeConnectorWorker)

- Script: `/home/jianliu/mk_bench/mk_kvbench.py` (on 96). Results: NFS
  `tgu01-pro-model-deployment/pd_disaggregation/results/mkbench_20260905/`.
- serve role: init engine → allocate → register → write ctl files (bare IP + actual RPC
  port, then registered ptrs/lens). bench role: read ctl files, register own buffers,
  exchange peer addresses, loop write/read iters, print JSON metrics.
- Handshake via generation control files in `/home/jianliu/mk_bench/ctl/`; a fresh
  generation ID per run also sidesteps stale processes/ports from dead containers.
- Buffers allocated with **raw `cudaMalloc` via ctypes, not torch** (gotcha c).
- Container: image default entrypoint (NOT `--entrypoint bash` for python),
  `--gpus --ipc host --network host --ulimit memlock=-1`,
  `--device /dev/infiniband/uverbs0/1 + rdma_cm`, `-e WITH_NVIDIA_PEERMEM=0`,
  runtime mounted `/opt/mooncake-runtime` + LD_LIBRARY_PATH (same as PD launch).

## Gotchas (all hit live, in debugging order)

a. `Found 0 HCAs` → `/dev/infiniband` not passed into container (same as PD item 1).
b. Registration `Bad address [14]` despite peermem=0 → memlock ulimit: `--cap-add
   IPC_LOCK` alone is NOT enough; `--ulimit memlock=-1` required.
c. **torch caching-allocator VAs randomly fail `ibv_reg_mr` with EFAULT** — every 3rd
   8 MB slab, worse at 16 MB, ≥32 MB always. Raw cudaMalloc registers 8/8 clean.
   Bench-only issue: vLLM KV tensors (cumem allocator) are unaffected.
d. **`batch_register_memory` phantom success**: returns 0 even when sub-MRs failed.
   Only symptom is a log line — `rdma_context.cpp:265 Failed to register ... Bad
   address` — and later transfers fail ret=-1. ALWAYS grep both logs for that line.
e. Slabs freed then VA-recycled can never re-register (stale MR cache) → keep every
   allocation alive for the whole run. Whole-slab "overlapped" ret=-7 is expected/harmless.
f. Init with a BARE IP. A hand-picked port in the init string is NOT the RPC listen port
   (dynamic under P2PHANDSHAKE) → peer must target `get_rpc_port()` read after init,
   else `Connection refused` with `parseHostNameWithPort ... port: 12001` (default).
g. Transfers need the PEER's registered addresses exchanged out-of-band; symmetric
   own-layout pointers only work by luck.
h. Bench container without `--gpus`: mooncake classifies buffers via
   `cudaPointerGetAttributes` → `driver insufficient (35)` even for CPU buffers.

## Interpretation template

real_PD_GB/s vs raw_GB/s: within ~2× ⇒ transport fine, serving path owns the gap;
raw also slow ⇒ suspect NIC/rail/MTU first. Run this bench before blaming hardware or
tuning connector knobs blindly.

Results written to Notion PD page 2026-09-05 (result + summary + key analysis style).
