---
name: remote-server-70-106
description: Use when accessing oemp106 10.10.68.106 8x RTX 6000D node.
version: 0.1.0
author: Hermes Agent
license: Proprietary
platforms: [linux]
metadata:
  hermes:
    tags: [GPU, RTX6000D, Blackwell, Remote, Server, WarpDrive, DSpark]
---

# Remote Server 10.10.68.106 (oemp106)

Access and management for server `oemp106` at `10.10.68.106` with **8× NVIDIA RTX 6000D** (Blackwell GB202, CC 12.0 / sm_120, 85,651 MiB each). Sibling of `oemp107` (10.10.68.107) — same hardware class and 68-net dual-homing.

**Key difference from 107: directly reachable from the WSL machine via SSH** (password auth) — no jump host through 68.96 required.

**Login change (2026-09-11, "for now"):** use `liujian` / `985202Qs~` — same account+password as 107. Old `jianliu`/`!QAZ2wsx` no longer authenticates (verified 0911; /home/jianliu leftover remains). **Sudo: GRANTED 2026-09-11** — qs ran `usermod -aG sudo liujian` (sudo group now qs,luojie,liujian); verified fresh-login `sudo -S whoami`=root with liujian's own password `985202Qs~`. **STILL NOT in docker group** (`docker ps` DENIED 0911) — docker work on 106 needs another sudoer/docker member or `sudo docker`.

**2026-09-23 (SSH-verified):** 68.87, 68.88, 68.90, 68.93, 68.94, 68.95, 68.96, 68.98 are now ALSO domain-joined — the same `liujian`/`985202Qs~` login works on all 8. Difference: **liujian has NO sudo on those 8** (`not in the sudoers file`) — 106/107 are the only ones with sudo so far. Old `jianliu`/`!QAZ2wsx` still authenticates on 96/98/93 but is rejected on 88/87/94/90/95. `/home/liujian` is missing only on 68.88.

## When to Use

- "Log in to 10.10.68.106 / oemp106"
- "What's running on 106?" (DSpark DS-V4-Flash, port 8001)
- "Check GPUs/disk on 106"
- "What's on /modelzoo on 106?"

## How to Run

From WSL directly (sshpass not installed locally — use pexpect):

```bash
# Canonical helper (umbrella skill) — PRIMARY since 2026-09-11: liujian/985202Qs~ (same as 107)
python3 ~/.hermes/skills/devops/remote-server-management/scripts/pexpect-ssh.py \
  10.10.68.106 liujian '985202Qs~' 'hostname && nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader' 30

# Old jianliu/'!QAZ2wsx' auth FAILS as of 2026-09-11
```

Or from jump host 68.96 (has sshpass 1.09):

```bash
ssh -o StrictHostKeyChecking=no jianliu@10.10.68.96 \
  "sshpass -p '985202Qs~' ssh -o StrictHostKeyChecking=no liujian@10.10.68.106 'command'"
```

## Quick Reference

| Item | Value |
|------|-------|
| Hostname | `oemp106` |
| OS | Ubuntu 22.04.4 LTS, kernel 5.15.0-190-generic |
| GPU | 8× NVIDIA RTX 6000D (Blackwell GB202, CC 12.0 / sm_120), PCI `10de:2bb9`, 85,651 MiB each |
| Driver | NVIDIA **610.43.02** (UNIX Open Kernel Module); `nvidia-smi` WORKS |
| CPU / RAM | 2× Xeon Gold 6530 (32c/socket, 128 threads), 1 TiB RAM |
| Disks | 98G root LVM (61G used) + 2× 3.5T NVMe → LVM `datavg-datalv` → **/home** (7.0T, 66G used) |
| NFS | `/modelzoo` = 10.10.68.79:/modelzoo (28T, 5.2T used) — cluster models; `/userdata` = 10.10.68.71:/data (14T) |
| Net mgmt | **retired 0923** — primary now `bond0 10.10.68.106/23` (default via 10.10.69.254); side net `ens35np0 192.168.100.106/24` |
| Net cluster | `10.10.68.106/23` on `bond0` (ens21f0np0 + ens21f1np1, 802.3ad LACP 2×25G); mooncake/VLLM_HOST_IP must use 10.10.68.106 |
| **RDMA** | **YES: `mlx5_bond_0` ConnectX-4Lx RoCE 25G PORT_ACTIVE (bond0)** + `mlx5_0` InfiniBand (DOWN). `/dev/infiniband/{uverbs0,uverbs1,rdma_cm,umad0,umad1}` present; `nvidia-peermem.ko` exists on host (not lsmod-loaded) |
| Docker | 29.7.2, root dir `/home/docker` (on 7T NVMe LVM), overlay2; **liujian NOT in docker group (0911)** |
| Sudo | **YES for liujian (2026-09-11: qs added to sudo group; `sudo -S whoami`=root verified, password `985202Qs~`)**; old jianliu sudo was rejected 0901 |
| Proxy | **None** (no proxy exports in .bashrc) |
| GitLab | No `~/.ssh/` on this node → no GitLab 10.10.50.23 key auth (107 has it, 106 does not) |
| Users | **Login: liujian (domain, uid 178201608, since 2026-09-11 — same creds as 107); sudo YES (0911 via qs usermod), docker group NO (0911)**. Old jianliu auth FAILS 0911 (home leftover exists). Also: docker, qs, xiaqing, liuchao, lixinwei, lixuechen, liyupeng, luojie, panyirong |
| Models | **No local models.** Serves from NFS `/modelzoo` (deepseekv4-flash-0731 156G/48 shards, glm_5_3_flash_fp8, glm_5_2_nvfp4, Kimi-K3, MiniMaxAI, Qwen3.x, wan2.2, qwen_image_2512, stable-diffusion-2-base, …) |

## Running Workload (2026-09-01)

**Container `dspark-v9-hybrid-fix6-180k`** (owner: xiaqing/qs — do not kill without asking):

- Image `10.10.91.56/sw2/fathomless-main-verify:gpu-smoke-fix6` (33.8GB), host network, `--gpus all`, Up 25h+
- Serves **DeepSeek-V4-Flash-DSpark** on port **8001** (all 8 GPUs, ~76.5GB used each, TP=8)
- vLLM `0.11.2.dev280+fathomless.firmament.v16` (cu132 build)
- DSpark speculative decoding: `--speculative-config {"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic"}`
- kv-cache fp8, block 256, `max_model_len=262144`, `gpu-memory-utilization 0.86`, FULL_AND_PIECEWISE cudagraphs, `FLASHINFER_MLA_SPARSE_DSV4` attention, async-scheduling, prefix caching, thinking=true / reasoning_effort=high defaults
- Model mount: `/modelzoo/deepseekv4-flash-0731` → `/models/DeepSeek-V4-Flash-DSpark`
- Overlay bind-mounts from `/home/xiaqing/tgu01_pro/tgu01-pro-model-deployment/deepseekv4_flash/overlays/vllm-hybrid-speculator/` → `/opt/venv/lib/python3.12/site-packages/` (hybrid_speculator.py, hybrid_autoload.py, hybrid_bootstrap.py, sitecustomize.py) + `/opt/vllm-hybrid`
- Check: `curl -s http://localhost:8001/v1/models`

## PD Disaggregation (vLLM + Mooncake) — WORKING, smoke-tested

Scripts in `/home/jianliu/pd_disaggregation/`: `start_pd_disaggregation.sh` (Prefill TP=4 GPUs 0-3 :8100 kv_producer, Decode TP=4 GPUs 4-7 :8200 kv_consumer, proxy :8000, bootstrap 8998), `stop_pd_disaggregation.sh`, `run_pd_test_flow.sh`. Baseline TP=8 results: `results/20260901_115149/summary.csv`.

**Smoke test PASSED 2026-09-02**: 3/3 prompts through proxy→prefill→RoCE RDMA KV→decode, 4/4 transfers OK, ~1 GB/s RoCE.

Critical config (ALL required — miss any and mooncake falls back to MNNVL transport → `cuMemExportToShareableHandle failed: 1` → send ret=-1 → decode EngineDeadError):

1. P/D containers need `--device=/dev/infiniband/uverbs0 --device=/dev/infiniband/uverbs1 --device=/dev/infiniband/rdma_cm` — docker passes /sys/class/infiniband but NOT /dev/infiniband by default → engine sees 0 HCAs
2. kv_connector_extra_config: `{"mooncake_protocol":"rdma","device_name":"mlx5_bond_0","num_workers":10}` (protocol default "tcp" also breaks)
3. kv_role: `kv_producer`/`kv_consumer` (kv_ prefix required by this image)
4. `--enable-cumem-allocator` on P/D (expandable_segments conflicts with connector)
5. Unset http_proxy/https_proxy in EVERY container (image bakes unreachable `http_proxy=10.10.60.185:7890`; aiohttp/httpx trust_env then hangs/fails on localhost calls)
6. Bootstrap connector patch bind-mounted: `mooncake_patch/mooncake/mooncake_connector.py` over in-image `/workspace/vllm/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/mooncake_connector.py` (retries transient bootstrap errors instead of killing the engine)
7. **`WITH_NVIDIA_PEERMEM=0` env on P/D containers (found 2026-09-04)** — default `ibv_reg_mr()` GPU-memory registration needs `nvidia_peermem` kernel module (NOT loaded on these hosts); without it every KV send fails with `rdma_transport.cpp:545 Memory region not registered by any active device(s)` → send ret=-1 → decode EngineDeadError. Value 0 switches to the DMA-BUF path, no module needed. Smoke after fix: 8/8 transfers @ 1689 MB/s on 68.96.
8. Watch for a blank line inside the backslash-continued `docker run` block in launch scripts — it silently truncates the command to `docker run requires at least 1 argument`.
9. Proxy :8000 returns 404 on `/health` and `/v1/models` by design; smoke prompts must use `"model":"DeepSeek-V4-Flash"` (the served-model-name), NOT the raw model path — the latter 404s on decode.
10. GDR/P2P verification recipe (2026-09-04): `WITH_NVIDIA_PEERMEM=0` + peermem `lsmod` refcount staying 0 across the run ⇒ DMA-BUF GPUDirect RDMA registration path (ibv_reg_mr-on-cuda-ptr path unused). Hard transfer proof: `rx_write_requests` delta on `/sys/class/infiniband/mlx5_*/ports/1/hw_counters/` (NOT top-level hw_counters; container needs no --gpus to read it but needs `--entrypoint bash` to skip the NGC banner). `nvidia-smi topo -p2p=w` all-OK = P2P capable; NCCL transport choice needs NCCL_DEBUG=INFO to prove. Even with peermem=0, GDR still applies: DMA-BUF is a GPUDirect path — "peermem module loaded" is NOT required for GPUDirect RDMA, only for the direct ibv_reg_mr(cuda_ptr) variant.
11. Standalone mooncake GPU-KV bench (`/home/jianliu/mk_bench/mk_kvbench.py` on 96, results `results/mkbench_20260905/`): raw loopback GPU→GPU RDMA on one CX-6 Dx 100G = **write 9.5-9.8 GB/s, read 11.9 GB/s** (76-95% line rate). Critical gotchas, all hit 2026-09-05: (a) initialize with BARE IP and advertise `get_rpc_port()` to the peer — a hand-picked port in the init string is NOT the RPC listen port (ephemeral) → Connection refused; (b) mooncake `batch_register_memory` returns 0 even when sub-MRs fail with EFAULT (phantom success — grep the log for `rdma_context.cpp:265 Failed to register`); (c) **torch-caching-allocator VAs randomly fail ibv_reg_mr with EFAULT (every 3rd 8MB slab; worse at 16MB; ≥32MB MRs always)** — allocate bench buffers with raw `cudaMalloc` via ctypes instead; (d) transfer needs the PEER's registered addresses (exchange via file), own-layout symmetric ptrs only work by luck; (e) containers need `--gpus --ipc host --ulimit memlock=-1 --device /dev/infiniband/uverbs1 --device /dev/infiniband/rdma_cm` and `-e WITH_NVIDIA_PEERMEM=0`.

Start: `MOONCAKE_PROTOCOL=rdma MOONCAKE_DEVICE=mlx5_bond_0 HOST_IP=10.10.68.106 MAX_MODEL_LEN=20480 IMAGE=10.10.91.56/sw2/fathomless-main-verify:gpu-smoke-fix6 bash start_pd_disaggregation.sh` (~4-6 min warm caches, ~20 min cold TileLang JIT).

## Pitfalls

- **Credentials since 2026-09-11: liujian / `985202Qs~` (same as 107)** — single-quote passwords (`!` triggers history expansion). liujian has sudo (0911, via qs) but is NOT in the docker group — use `sudo docker` if needed.
- **/userdata NFS read-only for uid 1005** — stage writable scripts under `/home/jianliu/`.
- **Container /dev/infiniband** — NOT passed through by default; explicit `--device` flags required for RDMA.
- **pkill self-match** — pkill patterns can match your own ssh remote shell; prefer exact container names via `docker rm -f`.
- **RTX 6000D is Blackwell sm_120** — driver/NCCL/Triton requirements differ from Ada nodes.
- Never kill foreign workloads without asking.

## Verification

```bash
python3 ~/.hermes/skills/devops/remote-server-management/scripts/pexpect-ssh.py \
  10.10.68.106 liujian '985202Qs~' 'hostname' 30
# Expected: oemp106 (verified 2026-09-11)
```
