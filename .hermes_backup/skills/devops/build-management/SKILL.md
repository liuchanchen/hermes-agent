---
name: build-management
description: Build and compile workflows for GPU-accelerated projects — vLLM fork building, CMake configuration, CUDA compilation, and handling China network restrictions for build dependencies.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Build Management

Umbrella skill for build and compilation tasks, especially CUDA-accelerated projects like vLLM forks on remote GPU servers. Covers build strategies, mirror configuration, CMake pitfalls, and dependency management under network constraints.

## Build Strategy Selection

### Option A: Host (Bare Metal) Compilation — RECOMMENDED
Direct venv-based compilation on the server. Faster iteration, no Docker layer caching issues.

```bash
# Prerequisites
sudo apt-get install -y --no-install-recommends g++-10 ninja-build ccache libibverbs-dev python3.12 python3.12-dev python3.12-venv
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Venv setup
python3.12 -m venv /path/to/venv
source /path/to/venv/bin/activate
pip install --upgrade pip

# PyTorch (match CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# Build tools
pip install cmake ninja wheel packaging setuptools-scm

# Build
export SETUPTOOLS_SCM_PRETEND_VERSION=0.6.0.dev0
MAX_JOBS=4 pip install -e . --no-build-isolation
```

### Option B: Docker Build — Use when isolation needed
Use for clean-room builds or reproducible environments. Higher risk of network issues in China.

## China Network Configuration

### Mirrors
| Resource | Mirror URL |
|----------|-----------|
| Ubuntu apt | `mirrors.aliyun.com` |
| PyPI | `mirrors.aliyun.com/pypi/simple/` or `pypi.tuna.tsinghua.edu.cn/simple/` |
| PyTorch CUDA 13.0 | `download.pytorch.org/whl/cu130` |
| GitHub proxy | `ghproxy.net` |
| NVIDIA CUDA | `developer.download.nvidia.cn` |

### Known Issues with Aliyun Mirror
- Some NVIDIA packages on Aliyun have SHA256 checksum mismatches
- **Fix:** Use Tsinghua mirror (`pypi.tuna.tsinghua.edu.cn`) or skip mirror with `--no-cache-dir`
- For PyTorch: use download.pytorch.org as primary index + Aliyun/Tsinghua as extra-index

## CMake Pitfalls

- **CMake version:** vLLM fork requires CMake ≥ 3.26; Ubuntu 22.04 ships 3.22 → use `pip install cmake`
- **CMake FetchContent** clones from GitHub (CUTLASS, Triton) — can timeout in China. **Preserve `.deps/` cache** — do not `rm -rf .deps`
- When `cmake` hangs or fails on FetchContent, check network/proxy first

## vLLM Fork Build (jasl/vllm ds4-sm120)

For the DeepSeek V4 fork at `github.com/jasl/vllm/tree/ds4-sm120`:

### Required CUDA dev packages (beyond cuda-nvcc)
```bash
sudo apt-get install -y cuda-nvrtc-dev-13-2 libcusparse-dev-13-2 libcusolver-dev-13-2 libcublas-dev-13-2
```

### Build command
```bash
export MAX_JOBS=4 SETUPTOOLS_SCM_PRETEND_VERSION=0.6.0.dev0
cd /path/to/vllm-source
pip install -e . --no-build-isolation --no-cache-dir
```

### Verification
```bash
python -c "import vllm; print(vllm.__version__)"  # Should print 0.6.0.dev0
```

## Cross-Server venv Sync & Rebuild

When multiple servers run the same vLLM fork with editable installs, see:
- **references/sync-venv-and-rebuild.md** — full workflow for comparing venvs, syncing source trees, rsync'ing `.deps/` to skip FetchContent git clone, and rebuilding with the correct host compiler.

## Pitfalls

- **Failing to `source ~/.bashrc`** on proxy servers → builds hang on GitHub/PyPI access
- **`--no-cache-dir`** important when mirror SHA256 issues are suspected
- **Docker layer caching** — modifying Dockerfile RUN layers invalidates cache; prefer host compilation for iteration
- **flashinfer** ~2GB wheel downloaded from GitHub Releases — use ghproxy.net proxy for China
- **CUDA dev packages** — minimal nvcc install does NOT include nvrtc, cusparse, cusolver, cublas dev headers; install separately
- **`cc1plus` not found (gcc-12/gcc-11 mismatch)** — On Ubuntu 22.04, `gcc` may default to gcc-12 but `cc1plus` (the C++ compiler backend) only exists for gcc-11. nvcc fails with `gcc: fatal error: cannot execute 'cc1plus'`. **Fix:** You need BOTH the env vars AND the cmake flag, because cmake invokes nvcc which has its own host-compiler path: `CMAKE_ARGS='-DCMAKE_CUDA_HOST_COMPILER=g++-11' CC=gcc-11 CXX=g++-11 pip install -e . --no-build-isolation`. Setting only `CC`/`CXX` is NOT enough — cmake's `-DCMAKE_CUDA_HOST_COMPILER` is what nvcc uses. Check with `find /usr/lib/gcc -name cc1plus` to see which gcc versions have it.
- **Runtime `cc1plus` failure (Triton/tilelang JIT)** — Even after a successful build with `CC=gcc-11 CXX=g++-11`, vLLM can crash at **runtime** during Triton or tilelang JIT compilation with the same `cc1plus` error. This happens because nvcc's runtime JIT compiler uses the system default `gcc` (not the build-time `CC`), and if `/usr/bin/gcc` → `gcc-12` without `cc1plus`, all JIT compilation fails. **Symptom:** `RuntimeError: #include <math_constants.h>` followed by `gcc: fatal error: cannot execute 'cc1plus'` in vLLM worker logs during model loading/profile_run. **Fix:** Make gcc-11 the system default: `sudo ln -sf gcc-11 /usr/bin/gcc`. Verify with `gcc --version | head -1`. This single fix covers both build-time and runtime. The `CC`/`CXX`/`CMAKE_ARGS` env vars are still needed for `pip install -e .` but the symlink ensures runtime JIT also works. **Important:** The symlink fix is the ONLY reliable solution for runtime JIT failures — `CMAKE_ARGS` and `CC`/`CXX` only affect the build, not runtime.
- **Editable install sync** — When vLLM is installed with `pip install -e .`, the source tree (e.g., `/data/vllm-ds4-sm120/`) is loaded directly at runtime. To sync code between servers, `scp` the changed `.py` files — no rebuild needed. Only C/CUDA extension changes (`.cu`, CMakeLists changes) require a full rebuild.
- **Venv vs source tree on remote servers** — Always check `python -c "import vllm; print(vllm.__file__)"` to confirm where vLLM actually loads from. The venv path and the source path are often different directories, and the source tree may be shared across venvs via editable installs.
- **Skip CMake FetchContent git clone with `.deps/` rsync** — CMake FetchContent (CUTLASS, Triton kernels, flash-attn) clones large repos from GitHub, which can take 30+ minutes on slow networks (e.g., servers with 100Mb/s ens20f0 bottleneck). If one server already has a successful build, rsync its `.deps/` directory to the target server before running `pip install -e .`. This completely skips the git clone phase. Example: `rsync -avz user@server88:/data/vllm-ds4-sm120/.deps/ /data/vllm-ds4-sm120/.deps/`. Use bond0/RDMA interface (e.g., 10.10.70.x or 192.168.66.x) instead of slow default routes for large transfers.
- **Comparing venvs across servers** — To diff packages between two remote venvs: `ssh host1 "source /path/venv/bin/activate && pip list --format=freeze"` and `ssh host2 "source /path/venv/bin/activate && pip list --format=freeze"`, then parse and diff programmatically. Key things to compare: vllm version, flashinfer version, torch version, transformers version.
- **Long remote builds: background + log** — For builds exceeding 5 minutes, run via SSH with output logged: `ssh host \"source venv/bin/activate && cd /src && pip install -e . --no-build-isolation > /tmp/build.log 2>&1 &\"`, then monitor with `ssh host \"tail -f /tmp/build.log\"` or `ssh host \"ps aux | grep nvcc | wc -l\"` and `ssh host \"find /tmp/tmp*.build-temp/ -name '*.o' | wc -l\"`. Do NOT use terminal foreground with long timeouts — the SSH session may hang.
- **vllm bench serve from remote client** — When benchmarking a vLLM server from a different machine, the `--model` flag is used both as the API model identifier AND to locate the local tokenizer. If the server's model path (e.g., `/data/models/deepseekv4_flash`) doesn't exist on the client, you must split the concerns: `--tokenizer` points to the client-local path, and `--served-model-name` matches the server's model ID. In the `run_vllm_bench_serve.sh` wrapper, set `BASE_URL=http://<server>:8000` and `SERVED_MODEL_NAME=/data/models/deepseekv4_flash` (the server path), while `MODEL` defaults to the client-local tokenizer path. Without `SERVED_MODEL_NAME`, vllm bench serve sends the local path as the model ID and the server rejects it.
