# PP0 Worker Silent Death — Diagnostic Pattern

**Updated**: 2026-06-03

## Symptom

2-node GLM-5.1-FP8 cluster (PP=2, TP=8) starts on both nodes, PP0 workers (ranks 0–7,
running on master 10.10.70.96) connect to NCCL successfully, PP1 workers (ranks 8–15,
running on worker 10.10.70.98) connect to NCCL, but the cluster hangs indefinitely at
the distributed barrier. No error is logged by PP0 workers before they appear to exit.
GPU memory on the master shows a diagnostic pattern:

```
GPU0:  ~14–17 MiB   ← PP0 worker died before model weight loading
GPU1: ~576 MiB     ← PP0 worker on GPU1–7 loaded model shard partially
GPU2: ~576 MiB
...
```

## Two Root Causes

### Mode A — Worker/master vLLM version mismatch (MOST COMMON)

Worker (70.98) running pre-built pip vLLM (v0.1.dev1) while master runs ds4-sm120
editable (v0.6.0.dev0). Workers crash during model loading with no log output.

**Fix**: See `enginecore-silent-death.md` — reinstall editable on worker.

**First diagnostic step** (run before anything else):
```bash
for node in 70.96 70.98; do
  echo "=== $node ==="
  ssh $node "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
done
```
Both must show `0.6.0.dev0+cu132` pointing to `/data/vllm-ds4-sm120/`. If versions differ,
this is Mode A.

### Mode B — gloo subgroup creation failure (LESS COMMON)

After NCCL init, workers call `init_model_parallel()` → `GroupCoordinator.__init__()`
which creates a `torch.distributed.new_group(ranks, backend="gloo")` CPU subgroup.
This uses the TCPStore (port 29505) to synchronize. If the TCPStore is unavailable
or PP0 workers fail at this point, PP0 workers silently exit — no Python exception
is raised, no ERROR is logged.

The PP1 workers (ranks 8–15) that already connected to NCCL then hang at the PP
barrier waiting for PP0 workers that will never respond.

## GPU Memory Diagnostic Pattern

| GPU | Memory Used | Meaning |
|-----|-------------|---------|
| GPU0 | 14–17 MiB | PP0 worker died before model shard allocation |
| GPU1–7 | ~576 MiB | PP0 workers on these GPUs attempted model loading but blocked at TP collective with GPU0 |

When ALL PP0 workers die before loading:
```
GPU0: 14 MiB, GPU1: 14 MiB, GPU2: 14 MiB, ... GPU7: 14 MiB
```
(no model loading at all)

## Active Questions (2026-06-02)

1. Is the `init_model_parallel()` → gloo subgroup creation failing on GPU0 specifically?
2. Does the same pattern occur with `PP=1` (single-node test)?
3. Is this related to the Blackwell-specific `disable_custom_all_reduce=True` or
   `enforce_eager` settings?
4. Can a single-GPU (TP=1) test isolate whether it's a GPU0 hardware issue or a
   distributed init issue?

## Debugging Steps

1. **Version verification first** (rules out Mode A):
   ```bash
   ssh 70.96 "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
   ssh 70.98 "source /data/venvs/vllm-ds4/bin/activate && vllm --version"
   ```

2. **Single-node single-GPU test** on master (70.96):
   ```bash
   ssh 70.96 "pkill -9 -f 'vllm serve'"
   ssh 70.96 "bash /data/model_startup_script/start_glm5_fp8_2node.sh master" &
   ssh 70.96 "nvidia-smi --query-gpu=index,memory.used --format=csv,noheader"
   ```
   Use `--tensor-parallel-size 1 --pipeline-parallel-size 1` for the single-GPU test.

3. **Add verbose logging**:
   - `NCCL_DEBUG=INFO` to see NCCL init completion per rank
   - `VLLM_LOGGING_LEVEL=DEBUG` for more initialization details
   - Add print in `parallel_state.py` `GroupCoordinator.__init__` before/after gloo subgroup creation

4. **Try without PP** (TP=8 only) to confirm the issue is PP-specific.