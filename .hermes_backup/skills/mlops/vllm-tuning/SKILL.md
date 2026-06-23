---
name: vllm-tuning
description: Use when tuning vLLM serving parameters for throughput and TTFT optimization on multi-node GPU clusters. Covers DeepSeek V4 Pro, GLM-5.1-FP8, and other MLA models on RTX PRO 6000 Blackwell (96GB/card) with TP/DP/EP/PP configurations, batched-tokens/seqs tuning, prefix caching, compilation strategies, and vllm bench serve methodology.
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [vllm, serving, throughput, ttft, tuning, deepseek, glm, blackwell, distributed, mla, flashinfer]
    related_skills: [remote-server-management, model-deployment]
---

# vLLM Serving Tuning

Umbrella skill for tuning vLLM server parameters to optimize throughput and TTFT on multi-node GPU clusters. Has absorbed model-specific deployment guides for GLM-5.1-FP8, DeepSeek V4 Pro, and general MLA-on-Blackwell issues from the former `glm5-fp8-blackwell` and `mla-blackwell` skills.

All three skills shared the same hardware (RTX PRO 6000 Blackwell, 2-node), same vLLM branch (ds4-sm120), same venv, same NCCL/RoCE infrastructure, and overlapping patches (compute capability, num_stages=1, indexer weight handling). They are now consolidated here as labeled subsections with model-specific detail in `references/` and `scripts/`.

## When to Use

- User asks to improve vLLM serving performance (throughput, TTFT, TPOT)
- Deploying DeepSeek V4 Pro, GLM-5.1-FP8, or other MLA models on multi-node Blackwell clusters
- Running vllm bench serve for systematic comparison
- Diagnosing vLLM startup failures (DP handshake timeouts, OOM, port conflicts, WorkerProc silent death)
- Testing prefix caching effectiveness
- Applying compute capability patches (CC 12.0) or workarounds for Blackwell MLA backends
- Patching triton_decode_attention.py for shared memory limits (num_stages=1)

## Cluster Environment

- **Model**: DeepSeek V4 Pro (~806GB total, fp8 quantized)
- **Nodes**: 70.96 (master) + 70.98 (worker), 8× RTX PRO 6000 Blackwell SE (96 GB/card) each
| **Interconnect** | RoCE v2 over ConnectX-6 Dx 100GbE via LACP bond (bond0, MTU 9000) |
- **NCCL**: IB Verbs via mlx5_0, GID index 3, timeout 23, TC 136
- **vLLM**: github.com/jasl/vllm ds4-sm120 branch (v0.6.0.dev0)
- **Model path**: /data/models/deepseekv4_pro
- **Venv**: /data/venvs/vllm-ds4

---

## References

See linked files for detailed information:

### Core vLLM Tuning
- `references/benchmark-methodology.md` — Standard test suite (S1/S2/S3), warmup requirements, metric interpretation
- `references/tuning-matrix.md` — Empirical results for all tested configurations. Actual TTFT/TPOT/throughput numbers. Best general-purpose: 8192/512 (Phase 2.5)
- `references/dp-handshake-timeout.md` — Root cause analysis and workarounds for the 5-minute DP handshake timeout in ds4-sm120 branch
- `references/pp-configuration.md` — PP=2 across 2 nodes: confirmed WORKING with VLLM_HOST_IP + NCCL RoCE v2. See Strategy Selection section for details.
- `references/nvfp4-memory-analysis.md` — NVFP4 checkpoint→GPU memory breakdown: why 22GB on disk = 30.4 GiB/GPU with TP=2 on RTX 5090, minimum TP=4 required for 32GB cards
- `references/memory-budget.md` — GPU memory estimation for DeepSeek V4 Pro on 96GB Blackwell cards
- `references/multi-node-dp-debugging-session.md` — Full debugging session log: --api-server-count+headless conflict, ZMQ port persistence, zombie VLLM:: cleanup
- `references/nccl-blackwell-compat.md` — NCCL 2.28.9 incompatibility with Blackwell sm120: error signature, fix (copy system 2.30.4 into venv), verification steps
- `references/vllm-bench-serve.md` — Accurate flag reference for vllm bench serve v0.6.0
- `scripts/startup-master.sh` — Template startup script for master node (DP mode)
- `scripts/startup-worker.sh` — Template startup script for worker node (DP mode)
- `scripts/startup-master-pp.sh` — Template startup script for master node (PP mode)
- `scripts/startup-worker-pp.sh` — Template startup script for worker node (PP mode)
- `scripts/bench-all.sh` — Run S1+S2+S3 in sequence with a single command
- `scripts/fix_flashinfer_mla_block_tables.py` — Apply block_tables squeeze patch for FlashInfer MLA sparse backend

### Blackwell CC 12.0 & MLA Backend Patches
- `references/blackwell-mla-patches.md` — Compute capability patches for 8+ MLA attention backend files (CC 9/10 → add 12)
- `references/mla-flashinfer-mla-debug.md` — FlashInfer block_tables shape mismatch traceback analysis and fix
- `references/mla-flashinfer-mla-sparse-sm120.md` — FlashInfer "compute capability not supported" on SM 12.0: rebuild fix

### GLM-5.1-FP8 Specific
- `references/glm5-nvfp4-bench-results.md` — Confirmed working benchmark commands and A1/A2/A3 results
- `references/glm5-nvfp4-bench-session.md` — Live benchmark session log with deadlock timeline and recovery procedure
- `references/glm5-bench-session.md` — GLM random dataset [gMASK] stall diagnosis
- `references/glm5-blackwell-vllm-compatibility.md` — Venv comparison, MoE backends, num_stages=1, venv compatibility matrix
- `references/glm5-deepseek-v2-indexer-wk-fix.md` — FP8 indexer weight fusion KeyError and weight-load skip guard
- `references/glm5-model-logits-debugging.md` — Garbled output diagnosis: weight integrity checks, indexer key inventory, is_v32 verification
- `references/glm5-pp0-silent-death-diagnostic.md` — PP0 worker silent death diagnostic (GPU memory pattern, version mismatch, gloo subgroup)
- `references/glm5-enginecore-silent-death.md` — Worker version mismatch causing silent EngineCore death
- `references/glm5-cli-flag-pitfalls.md` — reasoning-parser, tool-call-parser, hf-overrides interactions with GLM
- `references/glm5-tokenizer-garbled-output.md` — Detokenization investigation: standalone tokenizer vs server path
- `references/glm5-attention-backend-debugging.md` — Full backend compatibility table and error signature reference
- `references/glm5-flashinfer-mla-sparse-fp8-debugging.md` — XQA FP8 crash (bf16 vs fp8_e4m3 kv_cache dtype) root cause chain
- `references/glm5-index_topk-override-pitfall.md` — hasattr vs getattr pitfall with --hf-overrides
- `references/glm5-vllm-debug-session-2026-06-03.md` — Session log: NameError, AttributeError, shared memory OOM discoveries
- `references/glm5-vllm-workerproc-debug-session-2026-06-03.md` — WorkerProc init failure diagnostic sequence

---

## Strategy Selection

When deploying on 2 nodes with ds4-sm120 branch (v0.6.0.dev0), both strategies work, but PP=2+EP=8 is STRONGLY preferred when the correct NCCL env is set:

| Strategy | Parameters | Cross-Node? | Status |
|----------|-----------|------------|--------|
| **TP+PP+EP** | TP=8, PP=2, EP=8 | **Yes** (NCCL RoCE v2) | ✅ **Preferred**. Dramatically better prefix cache. |
| **TP+DP+EP** | TP=8, DP=2, EP=16 | Yes (DP coordinator) | ✅ Works. More complex handshake. |

### PP=2 DOES work across 2 nodes

The proven configuration is in the existing script at `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` on node 70.96.

**Key difference from naive attempt**: The multiproc executor defaults to `127.0.0.1` for distributed_init_method. PP across nodes requires the **`VLLM_HOST_IP`** env var to be set on each node:

```bash
# Master (70.96):
export VLLM_HOST_IP="10.10.71.96"

# Worker (70.98):
export VLLM_HOST_IP="10.10.71.98"
```

Plus the full NCCL RoCE v2 configuration (see the proven script for exact values). With these env vars, the NCCL workers discover each other across nodes correctly.

**PP=2 also still requires `--nnodes 2`, `--node-rank <0|1>`, and `--master-addr`/`--master-port`** — these set up the TCPStore for distributed initialization.

### PP vs DP: Prefix Cache is Decisively Better

**UPDATE (2026-05-26): Clean comparison with both on max-model-len=1M at 8192/128:**

| Metric | DP (8192/128) | **PP (8192/128)** | Improvement |
|--------|--------------|-------------------|-------------|
| S1 TTFT | 12.69s | **5.92s** | 53% faster |
| S2 60K TTFT | 260.5s | **188.8s** | 28% faster |
| S3 prefix TTFT | 142.8s | **43.2s** | **69% faster** |
| S3 throughput | 4.14 tok/s | **7.73 tok/s** | 87% more |
| S1 throughput | 48.2 tok/s | **67.4 tok/s** | 40% more |
| S1 TPOT | 108.6ms | **102.8ms** | 5% faster |

PP wins on EVERY metric. DP also crashed on 2/3 benchmarks with 8192/512 (API server OOM during long prompt decode), while PP completed 5/6 configs stably.

**Why PP beats DP for this setup:**
1. **PP coordinator is simpler**: DP requires a ZMQ coordinator process with 5-minute handshake timeout plus a DP coordinator process. Any failure on the worker side (OOM, config conflict) causes a cascading 5-minute stall.
2. **EP=8 vs EP=16**: PP uses half the expert parallelism, reducing expert routing table memory by ~40%, leaving more room for KV cache.
3. **Pipeline parallelism shares KV cache**: PP splits model layers across nodes, so each node only needs KV cache for its pipeline stage — less memory pressure per GPU.
4. **EP=16 with DP=2 fragments memory**: Each expert requires a routing table per node. With 16 experts × 2 DP ranks, that's 32 tables vs PP's 8 experts × 1 rank = 8 tables.

**Recommendation: PP is the default choice. Only consider DP if you have a specific reason the DP coordinator pattern is required.**

See `references/tuning-matrix.md` for complete results.

If DP handshake fails, the correct diagnosis path is in `references/dp-handshake-timeout.md`.

---

## Startup Scripts (Master, 70.96)

```bash
#!/bin/bash
# TP=8 + DP=2 + EP=16, batched-tokens=<B>, seqs=<N>
cd /data/venvs/vllm-ds4
source ~/.bashrc
source /data/venvs/vllm-ds4/bin/activate
rm -f /tmp/vllm_tp8_dp2.log
/usr/bin/nohup /data/venvs/vllm-ds4/bin/python3.12 /data/venvs/vllm-ds4/bin/vllm serve \
  /data/models/deepseekv4_pro --host 0.0.0.0 --port 8000 --trust-remote-code \
  --distributed-executor-backend mp --tensor-parallel-size 8 --pipeline-parallel-size 1 \
  --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend mp \
  --data-parallel-address 10.10.71.96 --nnodes 2 --node-rank <0|1> \
  --master-addr 10.10.71.96 --master-port 29505 --data-parallel-rpc-port 29550 \
  --enable-expert-parallel --kv-cache-dtype fp8 --block-size 256 \
  --max-model-len 1048576 --gpu-memory-utilization 0.93 \
  --max-num-seqs <N> --max-num-batched-tokens <B> \
  --compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE",\
    "compile_ranges_endpoints":[8192,16384,<B>]}' \
  --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice --reasoning-parser deepseek_v4 \
  --served-model-name deepseek_v4_pro > /tmp/vllm_tp8_dp2.log 2>&1 &
echo "PID:$!"
```

**Worker (70.98)**: Same command with `--headless --node-rank 1`.  
**Start order**: Worker FIRST, then master.  
**CRITICAL**: DO NOT put `--api-server-count 1` on the headless (--node-rank 1) node — it crashes with `ValueError: --api-server-count=1 cannot be used with --headless`. Only the master node (rank 0) gets `--api-server-count`.  
**PP mode**: Use `--pipeline-parallel-size 2` instead of `--data-parallel-*` flags. PP mode still requires `--nnodes 2`, `--node-rank <0|1>`, `--master-addr`/`--master-port`, and critically the **`VLLM_HOST_IP`** env var set to each node's real IP (10.10.71.96 for master, 10.10.71.98 for worker). PP also needs the full NCCL RoCE v2 configuration (NCCL_IB_HCA=mlx5_0, NCCL_NET=IB). See the proven script at `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh` and `scripts/startup-master-pp.sh`/`scripts/startup-worker-pp.sh` for correct PP templates.

**The proven script at `/data/venvs/vllm-ds4/start_dsv4_pro_2node.sh`** is the reference PP startup. It includes the exact NCCL env vars (NCCL_IB_HCA=mlx5_0, NCCL_IB_GID_INDEX=3, NCCL_IB_TIMEOUT=23, NCCL_IB_QPS_PER_CONNECTION=4, NCCL_IB_TC=136, NCCL_CROSS_NIC=0, NCCL_ALGO=Ring, NCCL_MIN_NCHANNELS=8, NCCL_NET=IB), VLLM_HOST_IP per-node, and the `-cc.pass_config.fuse_allreduce_rms=False` flag. The script uses `2>&1 | tee -a` (foreground pipe) so it blocks — run in background or a separate terminal. It logs to `/tmp/vllm_$1.log` where $1 is "master" or "worker".

For PP mode, **worker and master can start in either order** (both connect via TCPStore on 10.10.71.96:29505). The worker uses `--headless`.

**Worker start order for DP**: Worker FIRST, then master.

---

## PP vs DP: Apples-to-Apples (max-model-len=1M, 8192/128)

The cleanest comparison — both strategies completed all 3 benchmarks at max-model-len=1M:

| Metric | DP (TP=8+DP=2+EP=16) | **PP (TP=8+PP=2+EP=8)** | PP Advantage |
|--------|----------------------|-------------------------|--------------|
| S1 TTFT | 12.69s | **5.92s** | **2.1× faster** |
| S1 TPOT | 108.6ms | **102.8ms** | **5.3% better** |
| S1 throughput | 48.2 tok/s | **67.4 tok/s** | **40% more** |
| S2 60K TTFT | 260.5s | **188.8s** | **28% faster** |
| S3 prefix TTFT | 142.8s | **43.2s** | **3.3× faster** |
| S3 TPOT | 93.2ms | **81.0ms** | **13% better** |
| S3 throughput | 4.14 tok/s | **7.73 tok/s** | **87% more** |

**PP wins decisively.** DP also crashed on larger configs (8192/512 OOM on S2/S3), while PP completed 5 configs stably.

**Recommendation: Always use PP=2 unless you have a specific reason for DP.** See `references/pp-configuration.md` for required VLLM_HOST_IP + NCCL RoCE v2 setup.

See `references/tuning-matrix.md` for complete results.

## Key Hyperparameter Tuning Results

### PP mode (TP=8+PP=2+EP=8) — strongly preferred

| Config | S1 TTFT | S1 TPOT | S1 tok/s | S2 60K TTFT | S3 prefix TTFT | S3 TPOT | S3 tok/s |
|--------|---------|---------|----------|-------------|----------------|---------|----------|
| **8192/512** | **2.2s** | 99.7ms | 86.2 | 186.7s | 44.4s | 60.7ms | 7.15 |
| 8192/128 | 5.9s | 102.8ms | 67.4 | 188.8s | **43.2s** | 81.0ms | **7.73** |
| 8192/256 | **3.3s** | 105.5ms | 76.5 | **182.3s** | **43.9s** | 98.1ms | 7.41 |
| 16384/256 | 16.0s | 102.8ms | 44.0 | 197.5s | 48.5s | 56.4ms | 5.15 |
| 16384/128 | 16.3s | 102.4ms | 43.6 | 226.3s | 49.0s | 67.3ms | 7.08 |
| 16384/512 | **1.4s** | 99.5ms | **91.3** | (crashed) | (crashed) | — | — |

**Recommendation**: PP=2 at **8192/512** for general purpose. Use **8192/128** or **8192/256** for prefix-heavy workloads.

### DP mode (TP=8+DP=2+EP=16) — limited, only 8192/128 completed all 3 benchmarks at max-model-len=1M

| Config | S1 TTFT | S1 TPOT | S1 tok/s | S2 60K TTFT | S3 prefix TTFT | Status |
|--------|---------|---------|----------|-------------|----------------|--------|
| 8192/128 | 12.7s | 108.6ms | 48.2 | 260.5s | 142.8s | ✅ Only fully stable DP config |
| 8192/512 | 2.6s | 99.3ms | 83.9 | (crashed) | (crashed) | ⚠️ S1 only |

**Note on larger configs**: 32768+ batched-tokens or 512+ seqs at 16384+ batch all OOM on 96GB/card Blackwell due to KV cache pre-allocation exceeding 5-6 GiB available after model weights. DP=2 with EP=16 consumes more memory than PP=2 with EP=8, making DP less viable for 1M context.

**See `references/tuning-matrix.md`** for complete empirical data with per-config TTFT/TPOT/throughput figures.

---

## Critical Pitfall: Multi-Node Startup — Wrong IPs / RDMA Device Names

When starting a 2-node PP or DP cluster between 70.96 and 70.98, the startup scripts may reference IPs that do not exist:

- **10.10.71.x IPs do not exist** — No interface on either node has `10.10.71.96/98`. The actual RDMA IPs on bond0 are `192.168.66.10` (96) and `192.168.66.20` (98). Bon addresses in HEAD_IP, VLLM_HOST_IP, and MASTER_ADDR must use these.
- **GLOO needs an interface WITH an IP** — Setting `GLOO_SOCKET_IFNAME=ens35f0np0` (bond slave) causes `Unable to find address for: ens35f0np0` because the slave has no IP. Use `GLOO_SOCKET_IFNAME=bond0` which holds the actual IP.
- **RDMA device name differs per node** — On 70.96 the RDMA device is `rocep200s0f0`, on 70.98 it is `mlx5_bond_0` (due to RDMA bonding). If NCCL_IB_HCA=rocep200s0f0 is fixed in the script, it fails on 98 with `Failed to initialize any NET plugin`. Fix: auto-detect at runtime: `RDMA_DEV=$(rdma link show | head -1 | awk '{print $2}' | sed 's,/.*,,')`.

Also note: IPC ZMQ bind errors (`Cannot assign requested address`) when the VLLM_HOST_IP is not a local address — vLLM's ZMQ-based inter-process communication binds to VLLM_HOST_IP, so it must be a local interface IP.

## Critical Pitfall: Port 29505 Held by Zombie Workers After Crash

When vLLM crashes during startup (after worker processes have connected via TCPStore on port 29505), zombie `VLLM::Worker_PP*` processes can survive and continue holding port 29505 open. Subsequent restart attempts fail with:

```
DistNetworkError: The server socket has failed to listen on any local network address.
port: 29505, useIpv6: false, code: -98, name: EADDRINUSE
```

The zombie processes may not show up in a standard `ps aux | grep vllm` because their process names contain `VLLM::` prefix, not `vllm`:

```bash
# Check for survivors:
ps aux | grep VLLM::
ss -tlnp | grep 29505   # shows which PID holds the port

# Kill them:
kill -9 <PID>
```

**Best practice on restart**: Always check port 29505 before launching:

```bash
ss -tlnp | grep 29505 && echo "PORT IN USE - kill zombies first" || echo "port free"
```

## Critical Pitfall: MLA Models Do Not Work on Blackwell (CC 12.0)

This affects any model using **Multi-head Latent Attention (MLA)** — including DeepSeek V2/V3/V4 variants and **GLM-5.1-FP8** (GlmMoeDsaForCausalLM) — when deployed on Blackwell GPUs (RTX PRO 6000, compute capability 12.0).

### Blackwell CC 12.0 Issues Beyond Attention Backend Selection

Even after patching compute capability checks (see `references/blackwell-mla-patches.md`), other issues emerge:

**1. Triton MLA shared memory limit**: Blackwell SM 12.0 has 99 KB shared memory per block. The Triton MLA decode kernel requests 100 KB (102400 vs hardware limit 101376). Must use `--enforce-eager` to avoid CUDA graph warmup triggering the decoder kernel. Some batch sizes may still hit this at runtime.

**2. TRITON_MLA is the only working backend after patching**:
- `FLASHINFER_MLA` → XQA kernel requires 128 query heads/GPU (models with 64 heads + TP=8 have only 8/GPU)
- `CUTLASS_MLA` → does not support DECODER attention type
- `FLASHMLA` → `vllm._flashmla_C` not compiled for CC 12.0
- `FLASHINFER_MLA_SPARSE` → 3D page table vs 2D layout required by HND format
- **`TRITON_MLA`** → works with `--enforce-eager --block-size 64 --kv-cache-dtype auto`.
  > **`--kv-cache-dtype fp8` crashes**: Triton kernel `_fwd_grouped_kernel_stage1` requests
  > 100 KB shared memory, Blackwell SM 12.0 limit is 99 KB (101,376 bytes). Always use `auto`.

**3. Forcing non-sparse mode**: Models with `index_topk` in config.json trigger `is_v32=True` → `use_sparse=True`, which disables TRITON_MLA (sparse not supported). Fix: patch `deepseek_v2.py` lines 985/1216:
```python
self.is_v32 = hasattr(config, "index_topk") and getattr(config, "index_topk", 0) > 0
```
Then pass `--hf-overrides '{"index_topk": 0}'` at startup.

**4. Indexer FP8 weight fusion (GLM-specific)**: GLM checkpoints store indexer `wk.weight` + `wk.weight_scale_inv` as FP8. vLLM's `_try_load_fp8_indexer_wk` dequantizes into a fused `wk_weights_proj.weight` param. Three patches needed in `deepseek_v2.py`:
- Before `_try_load_fp8_indexer_wk`: `if not hasattr(self, "indexer") or (self.indexer is None and "indexer" in name): continue`
- Guard `params_dict[fused_name]` with `if fused_name not in params_dict: return False`
- Patch `is_v32` (point 3 above) so sparse is disabled and indexer isn't built

**5. GLM requires transformers v5**: The `glm_moe_dsa` model type is unrecognized by transformers v4.x:
```bash
pip install --upgrade 'transformers>=5.4.0'```

**6. Corrupt safetensors over nc/tar**: When transferring large checkpoints between nodes via `tar | nc`, shard files can be silently truncated. Verify all shards:
```python
from safetensors import safe_open
for f in sorted(glob.glob("model-*.safetensors")):
    with safe_open(f, "pt") as s: pass  # raises if corrupt
```

**Symptom**: vLLM engine initialization fails with:
```
ValueError: No valid attention backend found for cuda with AttentionSelectorConfig(
  head_size=576, dtype=torch.bfloat16, kv_cache_dtype=fp8, block_size=256,
  use_mla=True, ...
). Reasons: {
  FLASH_ATTN_MLA: [compute capability not supported, ...],
  FLASHMLA: [compute capability not supported, ...],
  FLASHINFER_MLA: [compute capability not supported, ...],
  TRITON_MLA: [sparse not supported],
  FLASHMLA_SPARSE: [compute capability not supported]
}
```

**Root cause**: All MLA attention backends in the `ds4-sm120` branch restrict compute capability to major version 9 (Hopper) or 10 (Blackwell v1). For example, `FlashMLABackend.supports_compute_capability` returns `capability.major in [9, 10]` — Blackwell CC 12 is excluded.

Additionally, models with `index_topk` in config.json (like GLM-5.1-FP8) trigger **sparse MLA** (`is_sparse=True`), which further limits backend choices since `TritonMLABackend` (the only CC-agnostic backend) does not support sparse mode.

**Fix**: Patch 8 files in the vLLM source + clear Python bytecode cache. See `references/blackwell-mla-patches.md` for the exact diff and patching procedure.

**No CLI flag workaround exists**: `use_sparse=True`, `kv_cache_dtype=fp8`, and `use_mla=True` are all auto-detected from the model config. There is no `--disable-mla` or `--disable-sparse` flag in the ds4-sm120 branch.

**Second blocker**: After passing the attention backend, GLM-5.1-FP8 weight loading fails with `KeyError: 'model.layers.39.self_attn.indexer.wk_weights_proj.weight'` — the FP8 indexer weight fusion path doesn't handle GLM's checkpoint layout. See `model-deployment` skill's `references/glm5-multi-node.md` for details.

**6. KV Cache dtype must match Blackwell expectations**: TRITON_MLA on Blackwell with --kv-cache-dtype auto (bf16) triggers a FlashInfer XQA MLA fallback that rejects non-fp8 inputs. Always use --kv-cache-dtype fp8 with TRITON_MLA on Blackwell.

**7. Garbled output with GLM (2026-06-02 root cause update)**: The garbled output is NOT a tokenizer issue.
Standalone `AutoTokenizer.decode()` and vLLM's `get_tokenizer().decode()` both return correct text.
The root cause is the **model forward pass producing near-random logits** (logprob ≈ -11.95 per token,
uniform over ~155K vocab). Model weights are intact (embedding std 0.009, bf16). Hypothesis:
`--hf-overrides '{\"index_topk\": 0}'` forces `is_v32=False`, which may collapse MoE expert routing
to random selection. Next step: test without `index_topk: 0` override or with `force_dense_mla` only.
See `references/glm5-model-logits-debugging.md` for full evidence.

## Critical Pitfall: NCCL "unhandled system error" on Blackwell (sm120)

On NVIDIA RTX PRO 6000 Blackwell SE (compute capability 12.0), NCCL 2.28.9 can produce a persistent `RuntimeError: NCCL error: unhandled system error` during `PyNcclCommunicator.__init__` → `self.all_reduce(data)` (line 142 of `pynccl.py`).

**Symptoms:**
- All 8 workers on the master node fail simultaneously with the same error
- Happens during `init_worker_distributed_environment` → `initialize_model_parallel` → `PyNcclCommunicator.__init__`
- IB link is ACTIVE (cat `/sys/class/infiniband/mlx5_0/ports/1/state` returns 4: ACTIVE)
- No zombie processes, no port conflicts, all GPUs idle
- Error persists across repeated kill/restart cycles
- Often triggered after repeated vLLM process kills (crash-loop scenario)
- Affects BOTH PP and DP modes — the NCCL all-reduce during communicator init is strategy-independent
- The error occurs on the master node ONLY (70.96). The worker (70.98) passes NCCL init fine.
- Once triggered, it persists across all subsequent restart attempts until a GPU reset

**Root cause:** Likely NCCL communicator state corruption on Blackwell after repeated process termination. The `nvidia_uvm` kernel module or NVLink bridge on sm120 may leave NCCL peers in a bad state after kill -9. The error originates from `cuda_communicator.py:75` → `PyNcclCommunicator.__init__` → `self.all_reduce(data)` — this is the first cross-GPU NCCL communication during init, and on Blackwell (sm120) the NCCL 2.28.9 runtime doesn't handle the stale peer state gracefully.

On these servers, gdm3 (GNOME Display Manager) runs Xorg, which also holds a GPU context, so `fuser` and `ps aux` may report no vLLM processes but the GPUs are still "in use by another client" from GDM's graphics session. Running `sudo systemctl stop gdm3` before `nvidia-smi -r` is required.

**Mitigations (in order of effectiveness):**
1. **Stop gdm3 then GPU reset** (requires root):
   ```bash
   sudo systemctl stop gdm3         # release GPU from X server
   sudo nvidia-smi -r              # reset all GPUs
   ```
   This is the ONLY reliable fix. System reboot also works.
2. **Temporary NCCL TCP fallback**: Set `NCCL_IB_DISABLE=1` and `NCCL_NET=Socket` to bypass IB verbs. This works but uses TCP over the 100GbE link instead of RDMA. Performance degrades significantly (especially for TP cross-node all-reduce).
3. **Increase idle time between kills**: Wait 10-15 seconds after all processes are dead and GPUs show 14 MiB before restarting. Sometimes the NCCL state self-recovers given sufficient idle time.
4. **Check for zombie VLLM:: processes**: `ps aux | grep VLLM::` — if any survive, kill them explicitly before restarting

**Note:** TCP fallback can be used to confirm the service starts correctly (NCCL initialization passes with Socket backend). The IB error is a system/NCCL state issue, not a configuration issue. After a successful reset + restart, restore IB backend and it works again.

**After GPU reset, gdm3 auto-restarts** (systemd will respawn it). The X server will re-initialize on the GPUs, which takes ~10-15s. Don't rush — wait for nvidia-smi to show steady 14 MiB per GPU before starting vLLM.

### NCCL 2.28.9 incompatibility with Blackwell (sm120) — "invalid usage" on ncclCommInitRank

After GPU reset, a different NCCL error can appear:
```
RuntimeError: NCCL error: invalid usage (run with NCCL_DEBUG=WARN for details)
```
This error occurs at `pynccl.py:135` → `ncclCommInitRank` — different from the `unhandled system error` above. The root cause is **NCCL 2.28.9 does not support Blackwell (compute capability 12.0)**.

**Environment**:
- System NCCL: 2.30.4 (`libnccl2` package, installed via apt)
- Venv NCCL (via PyTorch / nvidia-nccl-cu130 wheel): 2.28.9
- CUDA driver: 595.58.03, CUDA 13.2
- GPU: RTX PRO 6000 Blackwell SE (sm120)

**Fix** — copy the system NCCL .so into the venv:
```bash
# On each node:
cp /usr/lib/x86_64-linux-gnu/libnccl.so.2.30.4 \
  /data/venvs/vllm-ds4/lib/python3.12/site-packages/nvidia/nccl/lib/libnccl.so.2
cp /usr/lib/x86_64-linux-gnu/libnccl.so.2.30.4 \
  /data/venvs/vllm-ds4/lib/python3.12/site-packages/torch/lib/libnccl.so.2.30.4
cd /data/venvs/vllm-ds4/lib/python3.12/site-packages/torch/lib
ln -sf libnccl.so.2.30.4 libnccl.so.2
```

**Verification**: Start vLLM and check the log line:
```
vLLM is using nccl==2.30.4
```

If it still says `2.28.9`, the symlink was wrong. Verify with:
```bash
/data/venvs/vllm-ds4/bin/python3 -c "
from vllm.distributed.device_communicators.pynccl_wrapper import *
import ctypes, os
# Check which libnccl is actually loaded
print(os.path.realpath(ctypes.util.find_library('nccl')))
"

## Critical Pitfall: DP Handshake Timeout

ds4-sm120 branch (v0.6.0.dev0) has a **hardcoded 300s timeout** in `core.py:1046` for `DPEngineCoreProc.startup_handshake`. When the remote (headless) node fails to start its engine core, the master waits 5 minutes before timing out.

Most failures labelled "handshake timeout" are actually other issues:

**Pitfall 1: `--api-server-count 1` conflicts with `--headless`**
```
ValueError: --api-server-count=1 cannot be used with --headless
(no API servers are started in headless mode).
```
The headless worker node crashes at startup. Master then waits 5 minutes for a remote HELLO that will never arrive. **Fix**: Do NOT put `--api-server-count 1` on the headless (--node-rank 1) node.

**Pitfall 2: ZMQ port conflict (29550)**
```
ZMQError: Address already in use (addr='tcp://10.10.71.96:29550')
```
Previous vLLM processes leave the ZMQ port in TIME_WAIT. `fuser -k` may not catch it. **Fix**: `ss -tlnp | grep 29550` to confirm it's gone; if still present, `fuser -k 29550/tcp`.

**Pitfall 3: Zombie VLLM:: named processes hold CUDA memory**
After killing a vLLM host process, subprocesses named `VLLM::EngineCore_DP1`, `VLLM::Worker_DP1_TP*` may survive holding GPU memory. **Fix**: `ps aux | grep VLLM | awk '{print $2}' | xargs kill -9`

---

## /etc/hosts Pitfall (Ubuntu)

Ubuntu maps hostname to `127.0.1.1` by default. This causes Gloo to bind to loopback, breaking cross-node communication:

```bash
sudo sed -i '/<hostname>/d' /etc/hosts
echo '<real-ip>  <hostname>' | sudo tee -a /etc/hosts
```

---

## Benchmark Tips

### vllm bench serve — Correct Flag Reference (v0.6.0.dev0 ds4-sm120)

**Auth-protected servers** (`--api-key`): The benchmark tool sends requests to `/v1/completions` which require Bearer auth. Add `--header "Authorization: Bearer <key>"`. The wrapper script at `vllm_bench_standard_test/test_vllm_bench_serve.py` has been patched to support `--header` (append action, passes `--header` per item to `vllm bench serve`). Run via the wrapper, not direct `vllm bench serve` invocation:
```bash
bash run_vllm_bench_serve.sh \
  BASE_URL=http://<server>:8000 \
  MODEL=/data/models/<model> \
  SERVED_MODEL_NAME=<name> \
  BACKEND=openai \
  --header "Authorization: Bearer <key>"
```

**WRONG flags that silently fail:**
- `--concurrency` → **does not exist**, command exits 0 but produces no results
- `--dataset` (singular) → **ambiguous**, use `--dataset-name`
- `--output-json` → **does not exist**, use `--result-dir` + `--label`
- `--random-prefix-len` on `random` dataset only; on `prefix_repetition` the prefix is controlled separately
- Using filesystem path as `--model` with auth servers → **HTTP 401 Unauthorized**. Always use the served model name from `/v1/models`.

**Full working invocation template:**
```bash
/data/venvs/vllm-ds4/bin/vllm bench serve \
  --base-url http://localhost:8000 \
  --endpoint /v1/completions \
  --model glm5_1_fp8 \                     # MUST match /v1/models served name, NOT filesystem path
  --tokenizer /data/models/<model>/ \       # MANDATORY — no HF network from venv
  --dataset-name random|prefix_repetition \
  --max-concurrency 64 \
  --num-prompts 640 \
  --random-input-len 2048 \
  --random-output-len 512 \
  --temperature 0 \                        # MANDATORY — not default in ds4-sm120
  --disable-tqdm \
  --percentile-metrics ttft,tpot,itl \
  --metric-percentiles 50,90,99 \
  --save-result \
  --result-dir /data/bench_results \
  --label SCENARIO_NAME \
  > /data/bench_results/SCENARIO_NAME.log 2>&1 &
echo PID: $!
```

**prefix_repetition dataset flags** (for cache hit rate testing):
- `--prefix-repetition-prefix-len` — tokens cached per prefix (e.g., 512)
- `--prefix-repetition-suffix-len` — unique tokens per request (= input_len - prefix_len)
- `--prefix-repetition-output-len` — output tokens (e.g., 512)
- `--prefix-repetition-num-prefixes` — unique prefixes. Cache hit rate = (num_prompts - num_prefixes) / num_prompts
- For 60k input: `--prefix-repetition-suffix-len 59488` (60000 - 512)

### MANDATORY: --tokenizer Flag

The bench tool downloads a HuggingFace tokenizer at startup. If the venv has no external network (HuggingFace.co blocked, hf-mirror.com unreachable from venv), the tool hangs forever. **Always use `--tokenizer /data/models/<model>/`** pointing to the local model directory.

### MANDATORY: --model Flag Must Match Served Name

Using the filesystem model path as `--model` causes **HTTP 404 "Not Found" for all 640 requests**:
```bash
# WRONG — filesystem path → "Not Found":
--model /data/models/glm_5_1_nvfp4/

# CORRECT — served model name from /v1/models:
--model glm5_1_fp8
```

Find the served name with: `curl -s http://localhost:8000/v1/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"`

### Cache Hit Rate via prefix_repetition

The benchmark generates N unique prefixes and cycles through them across all `num-prompts` requests. Cache hit rate = (M - N) / M:

| Desired Cache Hit | N unique prefixes (M=640) | Formula |
|-------------------|--------------------------|---------|
| **0%** (all miss)  | `--prefix-repetition-num-prefixes 640` | N=M |
| **40%** hit        | `--prefix-repetition-num-prefixes 384` | (640-384)/640=0.40 |
| **80%** hit        | `--prefix-repetition-num-prefixes 128` | (640-128)/640=0.80 |

**prefix_repetition geometry**: prefix_len is CACHED (512 tokens); suffix_len = input_len - prefix_len is unique per request.

For 2k input: `--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536`
For 60k input: `--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 59488` (60000 - 512)

**Example commands** (M=640 prompts, output_len=512, conc=64, tokenizer mandatory):
```bash
# 0% cache: 640 unique prefixes
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 \
--prefix-repetition-output-len 512 --prefix-repetition-num-prefixes 640

# 40% cache: 384 unique prefixes (256 cache hits)
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 \
--prefix-repetition-output-len 512 --prefix-repetition-num-prefixes 384

# 80% cache: 128 unique prefixes (512 cache hits)
--dataset-name prefix_repetition \
--prefix-repetition-prefix-len 512 --prefix-repetition-suffix-len 1536 \
--prefix-repetition-output-len 512 --prefix-repetition-num-prefixes 128
```

**NOTE on `random` dataset with GLM models**: The `random` dataset stalls at `0/640` on GLM models (GLM-5.1-NVFP4, GlmMoeDsaForCausalLM) due to `[gMASK]` token being common in random sequences, triggering model deadlock. **Always use `prefix_repetition` for GLM models**, even for 0% cache (use `num-prefixes=640` with prefix_len=0).

**NOTE on `prefix_repetition` completed count**: The `completed` field in the result JSON equals `num_prefixes`, not total `num_prompts`. A run with `--num-prompts 640 --num-prefixes 384` (40% cache) will show `completed=384` in the JSON — the remaining 256 requests are warm cache-hit repetitions that don't appear individually. This is expected behavior, not a failure. Total wall-clock time and throughput are still measured across all 640 requests.

**NOTE on 60k+ token scenarios**: KV cache pressure scales as O(concurrency × max_context). At 64×60k tokens with output 512, total KV cache ≈ 64 × 60512 × 2 (k+v) × 2 bytes (bf16) ≈ 15.6 GB per GPU. This is manageable at conc=64, but at higher concurrency or with longer contexts, pre-allocation can exceed available GPU memory and cause OOM or serialization. Start with conc=64 and monitor `nvidia-smi` for memory pressure. If VRAM hits 99%, reduce `--max-concurrency` or `--gpu-memory-utilization`.

### Background Launch via setsid (CRITICAL)

Running `ssh host 'cmd &'` hangs because SSH waits for the background process. The working pattern:

```bash
ssh jianliu@10.10.70.96 "source ~/.bashrc && \
  setsid /data/venvs/vllm-ds4/bin/vllm bench serve \
    --tokenizer /data/models/<model>/ ... \
    </dev/null >/tmp/bench.log 2>&1 & echo LAUNCHED:\$!"
```

Verify: `ssh jianliu@10.10.70.96 "ps aux | grep 'vllm bench' | grep -v grep"` + check GPU util ~100%.

**HOWEVER**: `background=true` terminal exit code 0 only confirms the SSH command was sent — it does NOT confirm the benchmark completed. The `setsid` process forks and SSH exits while the benchmark continues.

**Correct completion monitoring pattern** — poll for the result JSON file, not process exit:

```bash
# WRONG: exit_code=0 but benchmark still running
ssh jianliu@10.10.70.96 "setsid cmd ... &"

# CORRECT: wait for JSON file to appear
ssh jianliu@10.10.70.96 "while true; do sleep 120; \
  if ls /data/bench_results/SCENARIO.json 2>/dev/null; then \
    echo SCENARIO_DONE; break; \
  else echo \"\$(date +%H:%M): still running\"; fi; done"
```

The 120s sleep interval balances responsiveness against poll frequency. With a 640-request benchmark at conc=64 taking 20–60 min, 120s is safe and won't trigger rate limits.

**GPU utilization as proxy health** — if JSON hasn't appeared but GPU util dropped to 0%, the process died silently. Always verify with `nvidia-smi` alongside the JSON check.

### CRITICAL Pitfall: `random` Dataset on GLM Models — Stalls at 0/640

On GLM-family models (GLM-5.1-NVFP4, GlmMoeDsaForCausalLM), the `random` dataset with `--random-prefix-len 0` causes the benchmark to stall at `0/640` with 100% GPU utilization — but no requests ever complete.

**Root cause**: The GLM tokenizer assigns `[gMASK]` (token ID that triggers "generative" mode) as one of the most common random token IDs. When `[gMASK]` is the first generated token, the model enters a mode that waits for a `sop` (start of planning) token, and without a valid second token, the prefill finishes but decode produces zero tokens — each request produces an empty completion.

**Symptom**: `0%| 0/640 [00:00<?, ?it/s]` in the log, but `nvidia-smi` shows 97-100% GPU utilization. The benchmark appears alive but no progress is ever made. Even a single CURL with `max_tokens=4` times out after 120+ seconds.

**Diagnosis path**:
1. `curl /v1/models` → responds normally (API server alive)
2. `curl /v1/completions` (max_tokens=4) → **hangs 120+ seconds** (engine core blocked)
3. `nvidia-smi` shows 97% GPU but zero actual tokens generated

**Fix**: Use `--temperature=0` to force greedy sampling and prevent the model from entering the special token generation mode. Even with `--temperature=0`, the `random` dataset still often generates `[gMASK]` as first token. The reliable fix is **do not use `random` dataset for GLM models** — use `prefix_repetition` dataset instead for all scenarios including 0% cache:

```bash
# For 0% cache on GLM models, use prefix_repetition with 640 unique prefixes:
--dataset-name prefix_repetition \
--prefix-repetition-num-prefixes 640 \         # 0% cache: all 640 prefixes unique
--prefix-repetition-prefix-len 0 \             # no cached prefix
--prefix-repetition-suffix-len 2048 \          # entire input is unique
--random-output-len 512
```

This avoids the `[gMASK]` token entirely by using real tokenizer-generated prompts.

**Alternative**: Supply a custom prompt file with `--dataset-name hf-chat` or `--dataset-name sharegpt` using real text prompts instead of random tokens.

### Throughput from Result JSON

TTFT/TPOT/ITL come from `--percentile-metrics`. **Throughput** is computed:
```python
import json
with open("result.json") as f:
    d = json.load(f)
total_out = sum(r["output_tokens"] for r in d["requests"])
total_time = d["total_time"]          # wall-clock seconds
throughput = total_out / total_time   # tokens/sec
```

### Benchmark Auth-Enabled Servers (--header flag)

When benchmarking a server with `--api-key` set (e.g., 70.95's MiniMax M2.7 server), `vllm bench serve` requires `--header` to pass the Bearer token. The `run_vllm_bench_serve.sh` wrapper does not natively support `--header` — patch `test_vllm_bench_serve.py`:

```python
# Add after extra_body parser:
parser.add_argument(
    "--header",
    action="append",
    default=None,
    help="HTTP header to pass with each request (e.g. Authorization:Bearer ***). Can be repeated.",
)
# Add in build_command():
if args.header:
    for h in args.header:
        command.extend(["--header", h])
```

Run benchmark targeting a remote auth-enabled server:
```bash
MODEL=/data/models/minimax_m2_7_nvfp4 \
TOKENIZER=/data/models/minimax_m2_7_nvfp4 \
SERVED_MODEL_NAME=minimax_m2_7 \
BASE_URL=http://10.10.70.95:8000 \
BACKEND=openai \
REQUESTS=200 CONCURRENCY=64 \
INPUT_TOKENS=2048 OUTPUT_TOKENS=500 \
CACHE_HIT_RATES=0,0.4,0.8 \
WARMUPS=0 SAVE_DETAILED=1 \
bash run_vllm_bench_serve.sh --header 'Authorization: Bearer <key>'
```

**API key retrieval**: Extract from running process cmdline: `cat /proc/$(pgrep -f 'vllm serve.*minimax_m2_7')/cmdline | tr '\\0' ' ' | grep -o 'api-key [^ ]*'`

### CRITICAL: `--temperature=0` Is Now Mandatory

`vllm bench serve` no longer defaults to `--temperature=0` for greedy decoding. The server-side default is model/API specific and may be non-zero, producing non-deterministic results.

**Always add** `--temperature=0` to every benchmark invocation:
```bash
--temperature=0 \
```

Failure to add this produces variable token sequences and misleading TTFT/TPOT measurements.

### CRITICAL: 60k+ Token Inputs at Concurrency ≥ 32 Hang the Server

**Conc=64 with 60k input → confirmed deadlock** (2026-06-04, 70.96):
- GPU spiked to 98% at 14:44, server hung by 14:45
- `/v1/models` continued responding (port 8000 alive), but `/v1/completions` timed out even for `max_tokens=4`
- Server did **NOT self-recover** (unlike the earlier A1 deadlock which recovered in ~2 min)
- Required `kill -9 <engine-pid>` + full restart
- Smoke test: single 60k request completes in ~7.5s TTFT — **1 request works, 64 concurrent hangs**

**Conc=32 with 60k input**: untested — use as starting point. If it hangs, reduce further.

**Conc=64 with 2k input**: safe (A1/A2/A3 all completed at conc=64 with 2k).

**Rule**: Failure threshold is a function of `(input_len × concurrency)`, not input_len alone. At 60k × 64 = 3.84M tokens total prefill — exceeds KV cache memory, causing NCCL collective deadlock during block allocation.

**Mitigation for 60k-class scenarios:**
1. Smoke test: `curl -d '{"model":"<model>","prompt":"...60k chars...","max_tokens":10}'` first
2. Reduce `--max-concurrency` to 8–16
3. Consider `--random-input-len 30000` as intermediate
4. Monitor GPU VRAM — full memory (~90 GiB) + 0% compute for >60s = in deadlock

**Recovery** when deadlocked: `kill -9 <engine-pid>` (e.g., PID 381662) — the engine process must be explicitly killed, not just the benchmark client. Server restart via startup script required.
- Smoke test a single request first: `curl -d '{"model":"glm5_1_fp8","prompt":"...","max_tokens":10}'` with 60k chars to confirm the server stays responsive
- At conc=64 with 2k input: safe. At conc=64 with 60k input: **dangerous**. The failure is a function of (input_len × concurrency), not input_len alone.

### Engine Deadlock: Partial API Response + 100% GPU

A vLLM server can be in a state where `/v1/models` responds, `/health` may return, GPU utilization is 97-100%, but `/v1/completions` and `/v1/chat/completions` both hang indefinitely (120+ second timeout even for 4 tokens). The engine core is deadlocked — GPU is computing but producing no output.

**Diagnosis**:
```bash
# These may still work:
curl -s --max-time 5 http://localhost:8000/v1/models       # likely OK
curl -s --max-time 5 http://localhost:8000/metrics         # likely OK

# This will hang:
curl -s --max-time 120 -X POST http://localhost:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<model>","prompt":"Hi","max_tokens":4,"temperature":0}'
# → timeout even for 4 tokens = engine core deadlocked
```

**Root cause evidence** (from log `/tmp/vllm_<name>.log`):
```
RuntimeError: Worker failed with error '[...gloo/transport/tcp/pair.cc:547]
  Connection closed by peer [<worker-ip>]:<port>'
vllm.v1.engine.exceptions.EngineDeadError: EngineCore encountered an issue.
```

This is a Gloo/NCCL inter-worker communication failure. The API server process is alive but the distributed engine workers have died. GPU remains at 100% because CUDA context is still held by zombie workers.

**Fix**: Full server restart required. `pkill -9` the API server AND all `VLLM::` named subprocesses (engine core, workers). See the GLM-5.1-FP8 Deployment section above for the restart procedure.

**Self-recovery timeline**: The engine can self-recover from this state without manual intervention. Observed on 70.96 (2026-06-04): after NCCL/Gloo pipe closure, `/v1/completions` timed out at 120s. The engine recovered on its own ~2 minutes later, and a subsequent `curl` returned in 0.182s confirming normal operation. A benchmark launched after recovery completed successfully (A1: 640/640 in 4561s). **Do not immediately restart** — wait 2-3 minutes before assuming permanent failure. If the server does not recover after 5 minutes, proceed with manual restart.

**Early warning sign**: The log shows `Avg generation throughput: 0.0 tokens/s` for an extended period while `Running: 1 reqs` — decode throughput of 0 tokens/s for >30s on a request with `max_tokens=16` means the engine is stuck.

### GPU Utilization as Process Health — 0% Does NOT Always Mean Deadlock

`nvidia-smi` showing 0% GPU utilization during a running benchmark is **NOT sufficient evidence of a crash**. Two distinct patterns:

**Pattern A — Deadlock (genuinely hung):**
- `/v1/models` responds, GPU VRAM full (~90 GiB), but `/v1/completions` hangs on even `max_tokens=4`
- Server self-recovers after 2-3 min OR requires `kill -9 <vllm-engine-pid>`
- Root cause: NCCL/Gloo inter-worker pipe closure or OOM during collective ops

**Pattern B — Serialized prefill (normal behavior):**
- GPU 0% in nvidia-smi snapshots between request batches, even with benchmark running
- Benchmark IS making progress (requests completing, results accumulating)
- `nvidia-smi` samples the GPU at a point in time — with `--disable-tqdm` and high memory pressure, requests serialize and the GPU idles between prefill batches
- A1 scenario (2k/0%, conc=64): GPU showed 0% in multi-minute sampling windows, but 640/640 completed successfully in 4561s
- **Distinguish by checking the result JSON or log**, not GPU util alone

**Reliable health check — verify with a simple request:**
```bash
timeout 10 curl -s -w 'T:%{time_total}s' -X POST http://localhost:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"glm5_1_fp8","prompt":"hi","max_tokens":4,"temperature":0}'
# DONE in <1s = server healthy
# timeout = engine core deadlocked
```

**If using `background=true` terminal for monitoring**, always set up a JSON-polling monitor too:
```bash
# Monitor that fires when result JSON appears
while true; do sleep 120; if ls /data/bench_results/SCENARIO.json 2>/dev/null; then echo DONE; break; fi; done
```
`exit_code=0` from `background=true` only confirms the SSH command was sent — the benchmark continues after SSH exits.

### Sequential Orchestration (Single Server)

All scenarios share one server. Run sequentially, kill leftovers between runs:
```bash
# Before next scenario:
ssh jianliu@10.10.70.96 "pkill -f 'vllm bench serve'; sleep 2"
```

- `references/glm5-bench-session.md` — Full GLM-5.1-NVFP4 stall diagnosis log (2026-06-04), including `random` dataset `[gMASK]` trap and working `prefix_repetition` commands for GLM models.
- `references/glm5-nvfp4-bench-results.md` — Confirmed working benchmark commands and actual results for A1/A2/A3 scenarios (2k input, 0/40/80% cache). Full `setsid` launch command template.
- `references/glm5-nvfp4-bench-session.md` — **2026-06-04 live session**: working A1/A2/A3 commands, B1 deadlock timeline, key mistakes (`--concurrency` vs `--max-concurrency`, model name vs path, GPU 0% normal vs deadlock), recovery procedure.

---

## GLM-5.1-FP8 Deployment (absorbed from `glm5-fp8-blackwell`)

Deploying GLM-5.1-FP8 (GlmMoeDsaForCausalLM, 256 routed experts, ~772B params, FP8) on 2-node Blackwell (RTX PRO 6000 SM 12.0, 96GB HBM) via vLLM ds4-sm120 branch. Architecture is DeepSeek V2 style with MLA + MoE.

### Required Config

```bash
--attention-config.backend=TRITON_MLA  # forces dense MLA; sparse backends fail on SM 12.0
--kv-cache-dtype auto                  # bf16 KV cache; TRITON_MLA bf16 path works on Blackwell
--enforce-eager                        # disables CUDA graph
--block-size 64
--max-model-len 65536
--gpu-memory-utilization 0.80
# NO --hf-overrides (counterproductive), NO --reasoning-parser glm45, NO --tool-call-parser glm47
```

### Required Code Patches (deepseek_v2.py)

All attention backends have `capability.major in [9, 10]` — extend to `[10, 12]`:
- `vllm/platforms/cuda.py` — `== 10` → `in [10, 12]`
- `vllm/v1/attention/backends/mla/*` — 8+ files (see `references/blackwell-mla-patches.md`)

Three-layer `is_v32=False` fix in `deepseek_v2.py`:
1. Patch `self.is_v32 = hasattr(config, "index_topk")` → `self.is_v32 = False` in DeepseekV2Attention.__init__ (2 places, lines ~990, ~1221)
2. Add `self.is_v32 = False` in DeepseekV2ForCausalLM.__init__ (line ~1384)
3. Add indexer-weight-skip in load_weights loop (line ~1541): `if not self.is_v32 and "indexer" in name: continue`

**CRITICAL syntax**: The indexer skip uses `"indexer"` (string literal), NOT `indexer` (bare variable). A bare variable causes `NameError` that's invisible in the master log — workers die silently with only `WorkerProc initialization failed`.

### Triton MLA Shared Memory — `num_stages=1`

Blackwell SM 12.0 has 99 KB shared memory/block; `num_stages=2` needs 100 KB. Patch `vllm/v1/attention/ops/triton_decode_attention.py`:
```python
content.replace('num_stages=2', 'num_stages=1')
```
After patching, verify syntax with `python3 -m py_compile` and sync to worker.

### Process Restart Sequence (2-node PP=2)

1. Kill ALL vLLM processes on both nodes (`pkill -9 -f 'vllm serve'` requires user consent)
2. Verify GPUs free (~97 GB/GPU) via `nvidia-smi`
3. Verify vLLM version consistent on both nodes (must be `0.6.0.dev0+cu132` from ds4-sm120)
4. Sync patched files to worker via scp
5. Apply NCCL 2.30.4 override if needed (see NCCL section above)
6. Start worker first (PP=2 requires PP1 bootstrap before PP0 proceeds):
   ```bash
   ssh 70.98 "bash /data/model_startup_script/start_glm5_fp8_2node.sh worker"
   ```
7. Then start master (wait ~20s):
   ```bash
   ssh 70.96 "bash /data/model_startup_script/start_glm5_fp8_2node.sh master"
   ```

### Known Issues (GLM-specific)

- **Port 29505 EADDRINUSE**: Previous TCPStore server holds the port. `fuser -k 29505/tcp` before restart.
- **Garbled output = indexer weights skipped**: Check token logprobs — near-uniform (~ -11.95 per token = log(154880)) confirms indexer weights not loaded. Fix: verify the 3-place is_v32=False patch and indexer-weight-skip are correctly applied.
- **GPU memory diagnostic**: GPU0=14 MiB + GPU1-7=~576 MiB → PP0 workers died silently (version mismatch or OOM).
- **WorkerProc init failure — finding the real error**: grep lines 85-150 of the log BEFORE the EngineCore wrapper messages:
  ```bash
  grep 'Worker_PP.*ERROR' /tmp/vllm_glm5_master.log | grep -v 'otel.py\|multiproc_executor.py' | head -5
  ```
- **`random` dataset stalls at 0/640 on GLM**: GLM tokenizer assigns `[gMASK]` as common random token, triggering generative mode decode deadlock. Always use `prefix_repetition` dataset.

See `references/glm5-model-logits-debugging.md`, `references/glm5-deepseek-v2-indexer-wk-fix.md`, `references/glm5-pp0-silent-death-diagnostic.md`, `references/glm5-enginecore-silent-death.md`, `references/glm5-cli-flag-pitfalls.md`, `references/glm5-tokenizer-garbled-output.md`, `references/glm5-attention-backend-debugging.md`, `references/glm5-flashinfer-mla-sparse-fp8-debugging.md`, `references/glm5-index_topk-override-pitfall.md`, `references/glm5-vllm-debug-session-2026-06-03.md`, `references/glm5-vllm-workerproc-debug-session-2026-06-03.md` for full details.

---

## MLA on Blackwell (absorbed from `mla-blackwell`)

Multi-Head Latent Attention deployment issues on Blackwell (SM 12.0) across models (GLM-5.1-FP8, DeepSeek V4 Pro). Both use ds4-sm120 branch at `/data/vllm-ds4-sm120/` with venv at `/data/venvs/vllm-ds4/`.

### FlashInfer block_tables shape mismatch

**Symptom**: `ValueError: block_tables must be 2D for shared paged KV layout, got ndim=3`
**Root cause**: `flashinfer_mla_sparse.py` line 358 unsqueezes `topk_indices_physical` to 3D, but FlashInfer 0.6.8.post1 expects 2D.
**Fix**: Patch to use safe squeeze:
```python
# flashinfer_mla_sparse.py line 358
block_tables=topk_indices_physical.squeeze(1) if topk_indices_physical.ndim == 3 else topk_indices_physical,
```
Apply via `scripts/fix_flashinfer_mla_block_tables.py`.

### Attention Backend Compatibility Matrix (SM 12.0)

| Backend | Dense/Sparse | fp8 kv | auto kv | Notes |
|---------|-------------|--------|---------|-------|
| TRITON_MLA | dense | ✓ | ✓ bf16 OK | **Only working dense backend** (with num_stages=1) |
| FLASHINFER_MLA | dense | ✓ | ✗ bf16 crash | Requires FP8; too few q-heads for 8-GPU TP |
| FLASHINFER_MLA_SPARSE | sparse | ✓ | ✗ bf16 crash | XQA fp8-only kernel; needs FlashInfer rebuilt for SM 12.0 |
| CUTLASS_MLA | dense | — | — | Doesn't support DECODER attention |
| FLASHMLA | dense/sparse | — | — | Not compiled for SM 12.0 |
| FLASH_ATTN_MLA | dense | — | — | CC 9 only |

**Key insight**: With `--kv-cache-dtype auto` (bf16), TRITON_MLA is the ONLY backend that works on Blackwell because its bf16 decode path fits within the 99 KB shared memory limit. All FlashInfer backends require FP8 on SM 12.0.

### Squeeze Patch Diagnostic Method

For deep vLLM internals errors, use binary search: progressively replace code with minimal no-op patches at each traceback location. The crash moves forward with each applied patch, revealing the next blocker:
- Squeeze at `MultiHeadLatentAttention.__init__` → crash moves to `init_device`
- Squeeze at `init_device` → crash moves to `make_layers`
- Squeeze at `make_layers` → reveals final blocker ("No valid attention backend")

See `references/mla-flashinfer-mla-debug.md` for full traceback analysis.

---

## vLLM Reasoning / Thinking Mode

### Server-Side Setup

Enable reasoning output with `--reasoning-parser`:
```bash
vllm serve zai-org/GLM-5.1-FP8 \
  --reasoning-parser glm45 \
  --tool-call-parser glm47 \
  --enable-auto-tool-choice \
  --chat-template-content-format=string
```

Parser names by model: `glm45` (GLM-5.x), `deepseek_r1` (DeepSeek-R1), `qwen3` (Qwen3), `granite` (IBM Granite 3.2).

### GLM-5.x Thinking Configuration

**Thinking is ON by default** for GLM-5/5.1. The `reasoning` field in the response contains thinking tokens.

```python
# Thinking ON (default)
resp = client.chat.completions.create(
    model="glm-5.1-fp8",
    messages=[{"role": "user", "content": "..."}],
    temperature=1, max_tokens=4096,
)
print(resp.choices[0].message.reasoning)  # thinking tokens
```

**Disable thinking** per-request:
```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
```

**GLM-5.x `reasoning_effort` levels:**
- `max` (default) — maximum thinking depth; used when unset or any non-`"high"` value
- `high` — reduced thinking, faster response, fewer tokens

```python
extra_body={"reasoning_effort": "high"}  # or "max"
```

**Server-level default** (all requests inherit unless overridden):
```bash
vllm serve MODEL --reasoning-parser glm45 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

**vLLM auto-mapping** of OpenAI `reasoning_effort` → `enable_thinking`:
- `reasoning_effort` = `"low"` / `"medium"` / `"high"` → `enable_thinking = true`
- `reasoning_effort` = `"none"` → `enable_thinking = false`
- `reasoning_effort` not set → preserves model default

**Thinking token budget** (limit thinking tokens):
```python
extra_body={"chat_template_kwargs": {"enable_thinking": True, "thinking_token_budget": 1024}}
```

### Hermes + Custom Provider Note

Hermes `agent.reasoning_effort` is **ignored by custom providers** (`is_custom_provider=True`). For custom vLLM endpoints, either set `--default-chat-template-kwargs` server-side or modify `agent/transports/chat_completions.py` to inject `reasoning_effort`/`chat_template_kwargs` into `extra_body`.

### Qwen3.6-35B-A3B-FP8 Single-Node Serving (70.98)

Startup script on 70.98: `~/work/tgu01-pro-model-deployment/qwen_3_6/start_qwen36.sh`

The default script uses `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7` with `--data-parallel-size 8`. For single-GPU serving, override with `CUDA_VISIBLE_DEVICES=0` (no DP flag needed — auto-detects TP=1).

```bash
# Single GPU
CUDA_VISIBLE_DEVICES=0 nohup vllm serve /data/models/Qwen3.6-35B-A3B-FP8 \
  --host 0.0.0.0 --port 8000 --trust-remote-code \
  --gpu-memory-utilization 0.95 \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' \
  > /tmp/vllm_qwen36.log 2>&1 &

# 4 GPUs (DP=4)
CUDA_VISIBLE_DEVICES=0,1,2,3 nohup bash ~/work/tgu01-pro-model-deployment/qwen_3_6/start_qwen36.sh
```

Model path on 70.98: `/data/models/Qwen3.6-35B-A3B-FP8` (35GB, copied from 70.88 `/data/models/Qwen3.6-35B-A3B-FP8`)
No `--reasoning-parser` or `--tokenizer-mode` flags needed for Qwen3.6 (unlike DeepSeek-V4/GLM).

### Qwen3.6-35B-A3B-NVFP4 Single-Node Serving (70.88)

Startup script on 70.88: `~/work/tgu01-pro-model-deployment/qwen_3_6/start_qwen36_nvfp4.sh`

Model path: `/data/models/Qwen3.6-35B-A3B-NVFP4/` (22GB on 70.88). Not available on 70.98.

**Critical OOM constraint on RTX 5090 (32 GB)**: The NVFP4 model requires ~30.37 GiB/GPU with TP=2, leaving only ~164 MiB free — not enough for KV cache or activation overhead. TP=2 on 32 GB cards is infeasible. Options:
- **TP=4 with 4 GPUs**: fits comfortably (~15 GiB/GPU for weights, ample KV cache room)
- **TP=1 on 32 GB**: also OOM — model weights alone exceed 31.36 GiB usable

Recommended flags for TP=4:
```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 nohup vllm serve /data/models/Qwen3.6-35B-A3B-NVFP4/ \
  --host 0.0.0.0 --port 8000 --tensor-parallel-size 4 --enable-expert-parallel \
  --trust-remote-code --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.92 \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' \
  > /tmp/vllm_qwen36_nvfp4.log 2>&1 &
```

**Critical Pitfall: FLASHINFER_DISABLE_VERSION_CHECK for NVFP4 on 70.88**

On 70.88, flashinfer-jit-cache (0.6.8.post1+cu130) mismatches flashinfer (0.6.11.post1). The `FLASHINFER_DISABLE_VERSION_CHECK=1` env var in the startup script may NOT propagate to vllm worker subprocesses. The error manifests as:
```
RuntimeError: flashinfer-jit-cache version (0.6.8.post1+cu130) does not match flashinfer version (0.6.11.post1)
```

**Root cause**: When vLLM uses `multiproc_executor`, worker processes are spawned via `multiprocessing.get_context("spawn")`. The `export` inside a bash script only applies to the script's own process — child processes spawned by Python's multiprocessing may not inherit it depending on how the env is constructed.

**Fix**: Export `FLASHINFER_DISABLE_VERSION_CHECK=1` in the shell BEFORE launching vllm, so it's in the parent process environment and inherited by all child workers:
```bash
source /data/venvs/vllm-ds4/bin/activate
export FLASHINFER_DISABLE_VERSION_CHECK=1
CUDA_VISIBLE_DEVICES=0,1,2,3 nohup vllm serve ...
```

Without this, the worker subprocesses fail the version check and the engine core initialization dies with `RuntimeError: Engine core initialization failed`. The error is NOT the usual OOM — check for "does not match flashinfer version" in the log before assuming memory issues.

**70.98 benchmark results — Qwen3.6-35B-A3B-FP8, 1 GPU:**

Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf

| Scenario | Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|-------------|-------------|----------------|----------------|
| Remote (70.88→70.98), 06-18 | 0% | 1800.7 | 9544.4 | 1,438 | 30.0 |
| Remote (70.88→70.98), 06-18 | 40% | 1824.5 | 9584.1 | 1,207 | 29.9 |
| Remote (70.88→70.98), 06-18 | 80% | 1801.4 | 9464.7 | 1,315 | 30.1 |

**70.88 benchmark results — Qwen3.6-35B-A3B-NVFP4, TP=2 (RTX 5090 32GB):**

Config: 2048 input tokens, 500 output tokens, concurrency=64, request-rate=inf

| Scenario | Cache Hit | Reqs | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|------|-------------|-------------|----------------|----------------|
| 200 reqs, 06-20 | 0% | 200 | 3045.0 | 15517.3 | 1,706 | 16.0 |
| 200 reqs, 06-20 | 40% | 200 | 3147.8 | 16041.0 | 1,312 | 16.2 |
| 200 reqs, 06-20 | 80% | 200 | 3170.6 | 16157.4 | 1,308 | 16.0 |

**70.88 benchmark results — Qwen3.6-35B-A3B-NVFP4, TP=2, single-batch (concurrency=1):**

Config: 2048 input tokens, 500 output tokens, 20 requests, concurrency=1, request-rate=inf

| Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) | Mean E2EL (ms) | Duration (s) |
|-----------|-------------|-------------|----------------|----------------|----------------|-------------|
| 0% | 261.0 | 1390.5 | 114.1 | 3.61 | 1915.2 | 38.3 |
| 40% | 259.8 | 1372.5 | 113.4 | 3.63 | 1924.0 | 38.5 |
| 80% | 261.1 | 1374.6 | 111.5 | 3.61 | 1914.7 | 38.3 |

**Key finding: Single-batch (conc=1) shows NO cache hit rate benefit.** Throughput, TTFT, TPOT, and E2E latency are nearly identical across 0%/40%/80% cache. With concurrency=1, requests are processed sequentially so there's no opportunity for cross-request KV cache prefix reuse. Each request completes before the next starts, so shared prefixes don't accumulate in the KV cache.

Compare with conc=64 results (same model): TPOT=16ms at conc=64 vs TPOT=3.6ms at conc=1 — the 4.4x increase is due to batch scheduling overhead under load, not cache effects.

**Recommendation**: Cache hit rate benchmarks require concurrency>1 to show meaningful differences. Single-batch tests measure raw per-request latency only.

**Single-batch benchmark command** (via remote script file to avoid SSH escaping issues):

```bash
# Write script to remote host to avoid env var escaping problems
ssh host 'python3 -c "
lines = [
    \"#!/bin/bash\",
    \"source /data/venvs/vllm-ds4/bin/activate\",
    \"export MODEL=/data/models/Qwen3.6-35B-A3B-NVFP4\",
    \"export TOKENIZER=/data/models/Qwen3.6-35B-A3B-NVFP4\",
    \"export TOKENIZER_MODE=auto\",
    \"export BASE_URL=http://127.0.0.1:8000\",
    \"export SERVED_MODEL_NAME=/model\",
    \"export MODEL_LABEL=qwen36_nvfp4_tp2\",
    \"export REQUESTS=20\",
    \"export CONCURRENCY=1\",
    \"export CACHE_HIT_RATES=0\",
    \"bash ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh\",
]
with open(\"/tmp/bench.sh\", \"w\") as f:
    f.write(chr(10).join(lines) + chr(10))
" && chmod +x /tmp/bench.sh && bash /tmp/bench.sh'
```

Key params for single-batch: `REQUESTS=20 CONCURRENCY=1 CACHE_HIT_RATES=0`.

**70.98 benchmark results — Qwen3.6-35B-FP8, 1 GPU (20260618_171729):**

Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf

| Scenario | Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|-------------|-------------|----------------|----------------|
| Remote (70.88→70.98) | 0% | 1800.7 | 9544.4 | 1,438 | 30.0 |
| Remote (70.88→70.98) | 40% | 1824.5 | 9584.1 | 1,207 | 29.9 |
| Remote (70.88→70.98) | 80% | 1801.4 | 9464.7 | 1,315 | 30.1 |

Qwen3.6-35B on 1 GPU delivers ~5x higher throughput and ~5x lower TPOT vs DeepSeek-V4-Flash on 4 GPUs, reflecting its much smaller active parameter count (~3B active, MoE architecture). Cache hit rate has minimal impact on Qwen3.6 — throughput is nearly flat across 0%/40%/80% scenarios.

**NVFP4 Memory Budget (Qwen3.6-35B-A3B-NVFP4 on RTX 5090 32GB):**

NVFP4 checkpoint is 22GB on disk but requires ~30.4 GiB/GPU with TP=2 — OOM on 32GB cards. The 22GB→30.4GiB gap comes from: fp8 block scales adding ~15% overhead (0.5625 bytes/param, not 0.5), bf16 activation workspace, CUDA graph capture, and KV cache reservation. TP=2 is infeasible on 32GB; TP=4 is the minimum. See `references/nvfp4-memory-analysis.md` for the full breakdown.

**Note on tokenizer-mode**: The `run_vllm_bench_serve.sh` wrapper defaults `TOKENIZER_MODE=deepseek_v4`. For Qwen3.6 models this is incorrect (should be `auto`). The benchmark still ran successfully because the tokenizer path was correct, but for accuracy, set `TOKENIZER_MODE=auto` when benchmarking non-DeepSeek models.

**Pitfall: SSH env var escaping for benchmark scripts**: When passing environment variables with special characters (paths with dots, hyphens, model names) via SSH, the shell may corrupt or truncate them. The `TOKENIZER_MODE=auto` assignment in particular gets sanitized by the terminal tool's security filter (replaced with `***`). Use a remote script file instead of inline env vars:

```bash
# WRONG: inline env vars may get corrupted by SSH/shell escaping
ssh host "export TOKENIZER=/data/models/Qwen3.6-35B-A3B-NVFP4 TOKENIZER_MODE=auto ..."

# CORRECT: write a script file on the remote host, then execute it
ssh host 'python3 -c "
lines = [
    \"#!/bin/bash\",
    \"source /data/venvs/vllm-ds4/bin/activate\",
    \"export MODEL=/data/models/Qwen3.6-35B-A3B-NVFP4\",
    \"export TOKENIZER=/data/models/Qwen3.6-35B-A3B-NVFP4\",
    \"export TOKENIZER_MODE=auto\",
    \"export BASE_URL=http://127.0.0.1:8000\",
    \"export SERVED_MODEL_NAME=/model\",
    \"export MODEL_LABEL=qwen36_nvfp4_tp2\",
    \"export REQUESTS=20\",
    \"export CONCURRENCY=1\",
    \"export CACHE_HIT_RATES=0\",
    \"bash ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh\",
]
with open(\"/tmp/bench.sh\", \"w\") as f:
    f.write(chr(10).join(lines) + chr(10))
\" && chmod +x /tmp/bench.sh && bash /tmp/bench.sh'
```

This avoids quoting issues and special-character sanitization in SSH command strings.

**Single-batch benchmark pattern** (latency measurement without queuing):

```bash
REQUESTS=20 CONCURRENCY=1 CACHE_HIT_RATES=0 \
  bash run_vllm_bench_serve.sh
```

This measures per-request latency (TTFT, TPOT, E2EL) under zero queuing — useful for comparing raw model serving speed without batch interference. Typical pattern: conc=1 TPOT is 4-5x lower than conc=64 TPOT for MoE models.

Results directory: `70.88:.../vllm_bench_results/20260618_171729/`

Results directory: `70.88:.../vllm_bench_results/20260618_171729/`

**Docker-based vLLM serving on 70.88 (Qwen3.6-35B-A3B-NVFP4):**

Docker image `vllm/vllm-openai:nightly` is available on both 70.88 and 70.98 (installed 2026-06-21 via deb packages from 70.88's aliyun mirror, transferred via rsync since download.docker.com is unreachable from 70.98).

Container startup on 70.88 (TP=2):
```bash
docker run -d --gpus '"device=0,1"' \
  -v /data/models/Qwen3.6-35B-A3B-NVFP4:/model:ro \
  -p 8000:8000 vllm/vllm-openai:nightly \
  --model /model --tensor-parallel-size 2 --trust-remote-code \
  --quantization modelopt --kv-cache-dtype fp8 --moe-backend marlin \
  --load-format fastsafetensors --gpu-memory-utilization 0.80 \
  --max-num-batched-tokens 8192 --enable-chunked-prefill \
  --language-model-only --reasoning-parser qwen3 --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'
```

Served model name inside container: `/model`. Use `SERVED_MODEL_NAME=/model` and `TOKENIZER=/data/models/Qwen3.6-35B-A3B-NVFP4` in bench scripts.

Cross-server benchmarking command (client on 70.88, server on 70.98):
```bash
ssh jianliu@10.10.70.88 "source /data/venvs/vllm-ds4/bin/activate && \
  MODEL=/data/models/Qwen3.6-35B-A3B-FP8 \
  TOKENIZER=/data/models/Qwen3.6-35B-A3B-FP8 \
  SERVED_MODEL_NAME=/data/models/Qwen3.6-35B-A3B-FP8 \
  MODEL_LABEL=qwen36_35b_fp8 \
  BASE_URL=http://10.10.70.98:8000 \
  bash /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh"
```

### DeepSeek-V4-Flash Single-Node Serving (70.88 and 70.98)

Startup script (on 70.88): `/home/jianliu/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`
Startup script (on 70.98): `~/work/tgu01-pro-model-deployment/deepseekv4_flash/start_dsv4_flash_1node.sh`

Key flags: TP auto-detected from `CUDA_VISIBLE_DEVICES` (default 8, set `CUDA_VISIBLE_DEVICES=0,1,2,3` for TP=4), EP, FP8 KV cache, `--reasoning-parser deepseek_v4`, `--tokenizer-mode deepseek_v4`, `--tool-call-parser deepseek_v4`, `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", "custom_ops":["all"]}'`.

Model path on 70.88: `/home/jianliu/work/models/deepseekv4_flash/` (149G, 46 safetensors)
Model path on 70.98: `/data/models/deepseekv4_flash/` (149G, 46 safetensors)

**70.98 benchmark results — TP=8, 1-node:**

Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf

| Scenario | Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|-------------|-------------|----------------|----------------|
| Remote (70.88→70.98), 06-17 | 0% | 350.1 | 1784.2 | 10,870 | 150.3 |
| Remote (70.88→70.98), 06-17 | 40% | 340.7 | 1736.5 | 12,043 | 152.7 |
| Remote (70.88→70.98), 06-17 | 80% | 401.5 | 2046.0 | 8,413 | 131.5 |
| Remote (70.88→70.98), 06-18 rerun | 0% | 304.9 | 1554.0 | 11,669 | 175.8 |
| Remote (70.88→70.98), 06-18 rerun | 40% | 361.6 | 1842.6 | 9,410 | 147.4 |
| Remote (70.88→70.98), 06-18 rerun | 80% | 403.2 | 2054.6 | 9,736 | 128.4 |
| Local (70.98→70.98), 06-18 | 0% | 316.1 | 1610.7 | 11,716 | 168.3 |
| Local (70.98→70.98), 06-18 | 40% | 358.8 | 1828.3 | 9,539 | 148.5 |
| Local (70.98→70.98), 06-18 | 80% | 386.4 | 1968.9 | 9,125 | 133.4 |

**70.98 benchmark results — TP=4 (4 GPUs), 1-node:**

Same config, `CUDA_VISIBLE_DEVICES=0,1,2,3`.

| Scenario | Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|-------------|-------------|----------------|----------------|
| Remote (70.88→70.98), 06-18 | 0% | 266.4 | 1357.5 | 16,780 | 195.7 |
| Remote (70.88→70.98), 06-18 | 40% | 312.5 | 1592.2 | 13,294 | 167.0 |
| Remote (70.88→70.98), 06-18 | 80% | 370.6 | 1888.5 | 11,186 | 139.0 |

TP=4 vs TP=8 comparison: ~15-25% lower throughput, ~55-60% higher TTFT at 0% cache.

**70.98 benchmark results — TP=4 (4 GPUs), 1-node, rerun (20260618_113728):**

Config: 2048 input tokens, 500 output tokens, 200 requests, concurrency=64, request-rate=inf, `CUDA_VISIBLE_DEVICES=0,1,2,3`

| Scenario | Cache Hit | Output tok/s | Total tok/s | Mean TTFT (ms) | Mean TPOT (ms) |
|----------|-----------|-------------|-------------|----------------|----------------|
| Remote (70.88→70.98), 06-18 rerun | 0% | 270.8 | 1380.2 | 15,962 | 193.4 |
| Remote (70.88→70.98), 06-18 rerun | 40% | 314.5 | 1602.8 | 13,210 | 165.8 |
| Remote (70.88→70.98), 06-18 rerun | 80% | 381.9 | 1946.1 | 9,614 | 136.9 |

Results directories:
- TP=8 remote: `70.88:.../vllm_bench_results/20260617_224213/` and `20260618_095259/`
- TP=8 local: `70.98:.../vllm_bench_results/20260618_101854/`
- TP=4 remote: `70.88:.../vllm_bench_results/20260618_105249/` and `20260618_113728/`
- Qwen3.6-35B-FP8 1-GPU remote: `70.88:.../vllm_bench_results/20260618_171729/`

**Cross-server benchmarking pattern** (client on 70.88, server on 70.98):
```bash
ssh jianliu@10.10.70.88 "source /data/venvs/vllm-ds4/bin/activate && \
  BASE_URL=http://10.10.70.98:8000 \
  SERVED_MODEL_NAME=/data/models/deepseekv4_flash \
  bash /home/jianliu/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh"
```
- `SERVED_MODEL_NAME` must match the server's model path (e.g., `/data/models/deepseekv4_flash`) — this is the model ID the server reports via `/v1/models`
- `MODEL` (default) points to the local tokenizer path on the client side (`/home/jianliu/work/models/deepseekv4_flash`)
- Without `SERVED_MODEL_NAME`, vllm bench serve sends the local `MODEL` path as the API model ID, which the server rejects with 404

**Local benchmarking pattern** (client and server on same 70.98):
```bash
ssh jianliu@10.10.70.98 "source /data/venvs/vllm-ds4/bin/activate && \
  MODEL=/data/models/deepseekv4_flash \
  BASE_URL=http://127.0.0.1:8000 \
  bash ~/work/tgu01-pro-model-deployment/vllm_bench_standard_test/run_vllm_bench_serve.sh"
```

### Critical Pitfall: cc1plus Not Found on gcc-12 Systems (70.98)

On 70.98, `/usr/bin/gcc` → `gcc-12` but `cc1plus` only exists for `gcc-11`. This causes **both build-time and runtime failures**:

1. **Build time**: `pip install -e .` fails — cmake/nvcc can't find host compiler. Fix: `CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11' CC=gcc-11 CXX=g++-11 pip install -e . --no-build-isolation`
2. **Runtime**: Triton/tilelang JIT compilation fails with `gcc: fatal error: cannot execute 'cc1plus'`. Fix: `sudo ln -sf gcc-11 /usr/bin/gcc` (makes gcc-11 the system default, matching g++-11 which already points to g++-11)
3. **Slow FetchContent on 100 Mb/s NIC**: CMake FetchContent clones CUTLASS, Triton kernels, flash-attn from GitHub. On 70.98's `ens20f0` (100 Mb/s), `triton_kernels` alone takes 30+ min. Fix: rsync `.deps/` from 70.88 (~30s for 2.6GB over 10GbE): `rsync -avz jianliu@10.10.70.88:/data/vllm-ds4-sm120/.deps/ /data/vllm-ds4-sm120/.deps/`, then `rm -rf build` (NOT `.deps/`) before rebuilding.

**70.88 NIC bottleneck**: `ens20f0` is stuck at 100 Mb/s (Fast Ethernet). Large model copies from 70.88 are capped at ~5 MB/s. Use `rsync -avz` from 70.88 → 70.98 for faster transfers over 10GbE.

## Verification Checklist

- [ ] SSH passwordless auth between nodes
- [ ] `/etc/hosts` maps to real IP
- [ ] Stale Python processes killed, ports 29505/29550 free
- [ ] GPU memory fully released (check for VLLM:: zombies)
- [ ] --api-server-count NOT set on headless node
- [ ] Worker started BEFORE master
- [ ] S1 warm-up run completes
- [ ] Prefix caching confirmed working (S3: ~47% expected over S2)
- [ ] Compile ranges match batched-tokens
