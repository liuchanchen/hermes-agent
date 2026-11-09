# Syncing vLLM venvs and Rebuilding Across Remote Servers

## Session: 2026-06-17

## Scenario

Two servers (70.88 master, 70.98 worker) running the same vLLM fork (`jasl/vllm ds4-sm120`) with editable installs from `/data/vllm-ds4-sm120/`. Need to sync 70.98's vLLM source and rebuild to match 70.88.

## Workflow

### 1. Compare venvs

```bash
# On each server:
ssh host "source /data/venvs/vllm-ds4/bin/activate && pip list --format=freeze"
```

Parse and diff programmatically (execute_code with dict comparison). Key differences to watch:
- vllm version string (editable installs show commit hash + date)
- flashinfer version (must match for serving)
- torch/CUDA toolkit versions
- Extra packages (sglang, tensorrt, etc. on one but not the other)

### 2. Sync source trees

Both servers use the same git commit (`b709b75 ds4-sm120`). 70.98 had local SM12 patches; 70.88 had a flash-attn-4 compatibility patch.

```bash
# Revert 70.98's extra patches
ssh jianliu@70.98 "cd /data/vllm-ds4-sm120 && git checkout -- ."

# Copy 70.88's patched files
scp jianliu@70.88:/data/vllm-ds4-sm120/vllm/model_executor/layers/rotary_embedding/common.py \
    jianliu@70.98:/data/vllm-ds4-sm120/vllm/model_executor/layers/rotary_embedding/common.py
```

Verify with `git diff --stat` on both servers.

### 3. Skip FetchContent git clone with `.deps/` rsync

CMake FetchContent clones CUTLASS (~500MB), Triton kernels (~500MB+), flash-attn, etc. from GitHub. On 100Mb/s networks this takes 30+ minutes and can hang.

**Solution:** rsync `.deps/` from the server that already built successfully:

```bash
# From 70.88 (which has a working build) to 70.98:
rsync -avz --progress jianliu@10.10.70.88:/data/vllm-ds4-sm120/.deps/ \
    jianliu@10.10.70.98:/data/vllm-ds4-sm120/.deps/
```

- 2.6GB transferred in ~30 seconds over 10GbE (vs 30+ min git clone)
- SSH key auth required: 70.88→70.98 works, but 70.98→70.88 does NOT (no key set up)
- Use `ssh-keyscan -H <ip> >> ~/.ssh/known_hosts` first if host key is unknown

### 4. Build with correct host compiler

```bash
ssh jianliu@70.98
source /data/venvs/vllm-ds4/bin/activate
cd /data/vllm-ds4-sm120
rm -rf build   # clean stale cmake cache (NOT .deps/)
CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11' CC=gcc-11 CXX=g++-11 \
    pip install -e . --no-build-isolation > /tmp/vllm_build.log 2>&1 &
```

**Critical:** `CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11'` is required even when `CC=gcc-11 CXX=g++-11` is set, because cmake invokes nvcc which has its own host-compiler path.

### 5. Monitor build progress

```bash
# Check if compilation is active
ssh host "ps aux | grep nvcc | grep -v grep | wc -l"

# Count compiled object files
ssh host "find /tmp/tmp*.build-temp/ -name '*.o' | wc -l"

# Build log tail
ssh host "tail -5 /tmp/vllm_build.log"

# Check process
ssh host "ps -p <PID> -o etime="
```

### 6. Verify

```bash
ssh host "source /data/venvs/vllm-ds4/bin/activate && python -c 'import vllm; print(vllm.__version__); print(vllm.__file__)'"
```

## Key Facts

- 70.98 has gcc-12 as default `gcc` but only gcc-11 has `cc1plus` → must use g++-11 explicitly
- `.deps/` contains: cutlass-src, cutlass-build, triton_kernels-src, triton_kernels-build, deepgemm-*, flashmla-*, qutlass-*, vllm-flash-attn-*
- Editable install means `.py` file changes take effect immediately; only `.cu`/CMakeLists changes require rebuild
- Build with `-j 128` (auto-detected by ninja on 128-core server) takes ~15 min for CUDA kernels after deps are resolved
- Version string changes on rebuild: `0.1.dev1+gb709b75b4.d20260518.cu132` → `0.1.dev1+gb709b75b4.d20260617.cu132` (date updates)
