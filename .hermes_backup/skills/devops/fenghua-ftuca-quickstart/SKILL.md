---
name: fenghua-ftuca-quickstart
description: Deploy vLLM on Fenghua GR308S MAX via FTUCA stack.
version: 0.1.0
author: Hermes
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Fenghua, FTUCA, GR308S, vLLM, FANTGPU]
---

# Fenghua GR308S MAX FTUCA Quick Start

Quick-start for the FTUCA software stack on Fenghua (风华三号 / FANTGPU) GR308S MAX cards: install/uninstall the driver stack .run file, configure the fantasy docker/containerd runtime, import the vLLM image, run inference, monitor GPUs with `fantgpu-smi`, and deploy on Kubernetes with the device-plugin + fantasy-exporter. Source: 《GR308S_MAX FTUCA 快速上手指南_V1.8》(2026-03-18), at `/mnt/c/Users/liuch/Documents/warpdriveai/TGU01/TGU01-F/`. This does NOT cover the WarpDrive TGU01-Pro stack (`wd-smi`) — those are different platforms; see `remote-server-management`.

## When to Use

- Setting up a bare Fenghua GR308S MAX / TGU01-F node to run vLLM inference
- Installing or upgrading/downgrading the FTUCA software stack (`.run` installer)
- Configuring the `fantasy` docker or containerd runtime for GPU containers
- Importing the vLLM / FantRT docker image into a node
- Building a host (non-container) vLLM inference env on the FTUCA SDK
- Checking/monitoring GR308S MAX GPU state with `fantgpu-smi`
- Deploying Fenghua GPUs on a K8s cluster (device-plugin, fantasy-exporter, `fantasy.com/gpu`)

## Prerequisites

- Delivery packages (from 风华创智 technical support):
  - `fantgpu-fh3_Linux-Debian_1.x.x.x-compute_x86_64.run` — software-stack installer (DDK, driver, SMI, container_toolkit)
  - `fantgpu-fh3-docker-image_1.x.x.x-compute.tar` — docker image bundle (`ftuca-*` and `fantrt-*` subdirs)
  - `fantgpu-fh3-cloud-native_1.x.x.x.tar` — cloud-native plugin bundle (device-plugin + exporter yaml/images; single-node debug can ignore)
- Host: Intel/AMD server, Ubuntu-22.04-server, kernel 5.15 ~ 6.8
- ≥1 GB free disk before running the installer (`df -m` to check)
- Docs use FTUCA `1.1.0.10` as the example version — swap the version in filenames/commands to match yours
- Model usage guides: https://gitee.com/fantasyxpu/modelzoo (FantasyModelZoo — click a model for its env/deps/download/inference page)
- Per-card note: one physical GR308S MAX card exposes **2 GPU nodes** (dual-die). N cards → 2N GPU nodes. The user's TGU01-F test node has a `vllm:1.1.0.16-py310-ubuntu22.04` image already loaded.

## How to Run

Reach the node and run commands via the `terminal` tool over SSH (password auth, `pexpect-ssh.py` from `remote-server-management` when no sshpass). Root is required for `dpkg -P` and runtime config; `fantgpu-smi` works from any shell once the stack is installed. Frame each step below as an SSH command; verify after each stage per the Verification section.

## Quick Reference

```bash
# install / uninstall stack (.run must be run from its directory)
bash fantgpu-fh3_Linux-Debian_1.x.x.x-compute_x86_64.run --all -i   # 5 comps → expect 5× [INFO] install success
bash fantgpu-fh3_Linux-Debian_1.x.x.x-compute_x86_64.run --all -u   # uninstall (need old .run on disk)
dpkg -l | grep fantgpu                                               # list installed ftuca components
dpkg -P fantgpu-container-toolkit fantgpu-fh3 fantgpu-smi            # uninstall method 2 (as root)

# GPU checks / monitoring
fantgpu-smi                                  # node count check, full status
fantgpu-smi --loop xx                        # refresh every xx seconds
fantgpu-smi --loop xx --filename FILE        # loop + dump to file

# docker runtime
apt install docker.io
fantasy-ctk runtime configure --set-as-default && systemctl restart docker
fantasy-ctk runtime remove && systemctl restart docker              # cleanup only

# containerd runtime (cluster)
fantasy-ctk runtime configure --runtime containerd --set-as-default && systemctl restart containerd
fantasy-ctk runtime remove --runtime containerd                     # cleanup

# import images
tar -xvf fantgpu-fh3-docker-image_1.x.x.x-compute.tar
docker load -i vllm-1.x.x.x-py310-ubuntu20.04.tar    # → vllm 5.94GB
docker load -i fantrt-1.x.x.x-py310-ubuntu20.04.tar  # → fantrt 2.78GB

# host (non-container) vLLM env
conda create -n XXX python=3.10 && conda activate XXX
pip install numba
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
cd /opt/fantasy/ftuca_sdk/wheel/ && pip install *

# cluster plugins
tar -xvf fantgpu-fh3-cloud-native_1.x.x.x.tar
find "fantgpu-fh3-cloud-native_1.x.x.x/" -name "*.tar" | xargs -I {} docker load -i {}
find "fantgpu-fh3-cloud-native_1.x.x.x/" -name "*.tar" | xargs -I {} ctr -n=k8s.io images import
kubectl apply -f fantasy-device-plugin_v1.x.x.x.yaml
kubectl apply -f fantasy-exporter_v1.0.0.5.yaml
kubectl get pod -n fantasy-device-plugin | grep device-plugin
kubectl describe nodes | grep Capacity -A15           # look for fantasy.com/gpu
curl http://<node>:32021/metrics                       # exporter default port
```

## Procedure

### 1. Install / upgrade the software stack
```bash
cd <dir-with-run-file>
bash fantgpu-fh3_Linux-Debian_1.x.x.x-compute_x86_64.run --all -i
```
Expect exactly **5** `install Success` prints (one per component). Any `failed` → contact support. **Reboot after driver install.** If an older FTUCA version is present, uninstall it first (method 1: run the old `.run` with `--all -u`; method 2: `dpkg -P fantgpu-container-toolkit fantgpu-fh3 fantgpu-smi` as root — names are the 2nd column of `dpkg -l | grep fantgpu`).

### 2. Check GPU state
```bash
fantgpu-smi
```
Each physical card should list 2 GPU nodes. Wrong node count or errors → contact support before proceeding.

### 3. Configure container runtime + import images (single-node debug → docker)
```bash
apt install docker.io
fantasy-ctk runtime configure --set-as-default
systemctl restart docker
tar -xvf fantgpu-fh3-docker-image_1.x.x.x-compute.tar
cd fantgpu-fh3-docker-image_1.x.x.x-compute/ftuca-1.x.x.x-py310-ubuntu20.04
docker load -i vllm-1.x.x.x-py310-ubuntu20.04.tar
# optionally the FantRT image:
cd ../fantrt-1.x.x.x-py310-ubuntu20.04 && docker load -i fantrt-1.x.x.x-py310-ubuntu20.04.tar
docker images   # verify vllm + fantrt tags
```
Runtime configure is one-time — no need to repeat unless you removed it.

### 4. Run inference
Open the model's guide at https://gitee.com/fantasyxpu/modelzoo and follow its env/deps/download/inference steps inside the vLLM container (or the host env from section 5).

### 5. Host (non-container) vLLM env
```bash
conda create -n XXX python=3.10 && conda activate XXX
pip install numba
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
cd /opt/fantasy/ftuca_sdk/wheel/ && pip install *
```
Then follow the same modelzoo guide inside this venv unreservedly (no container needed).

### 6. Cluster deployment (K8s)
Node nodes only need the FTUCA stack + cloud-native plugin (master is management-only):

1. Install FTUCA per Procedure 1-2 on each Node.
2. Runtime: if docker, see step 3; if containerd:
   ```bash
   fantasy-ctk runtime configure --runtime containerd --set-as-default
   systemctl restart containerd
   ```
3. Import plugin images:
   ```bash
   tar -xvf fantgpu-fh3-cloud-native_1.x.x.x.tar
   # docker runtime:
   find "fantgpu-fh3-cloud-native_1.x.x.x/" -name "*.tar" | xargs -I {} docker load -i {}
   # containerd runtime:
   find "fantgpu-fh3-cloud-native_1.x.x.x/" -name "*.tar" | xargs -I {} ctr -n=k8s.io images import
   ```
4. On the Master, apply yaml (files are inside the cloud-native tar — copy it to master):
   ```bash
   kubectl apply -f fantasy-device-plugin_v1.x.x.x.yaml
   kubectl get pod -n fantasy-device-plugin | grep device-plugin   # all Running
   kubectl apply -f fantasy-exporter_v1.0.0.5.yaml
   kubectl get pod | grep -i fantasy-exporter                       # all Running
   ```
5. Verify GPU registration + metrics:
   ```bash
   kubectl describe nodes | grep Capacity -A15    # fantasy.com/gpu must equal 2×cards per node (e.g. 4)
   curl http://10.0.xx.xx:32021/metrics           # e.g. fant_chip_hotspot_temp{...}
   ```
6. Example pod spec (GPU scheduling uses the `fantasy.com/gpu` resource):
   - `smi-test` Deployment: `replicas: 4`, each requesting `fantasy.com/gpu: 2`, image `vllm:*`, `command: ["sleep","3600"]`, nodeAffinity to your nodes. Verify with `kubectl exec -it <pod> -n test -- fantgpu-smi` (each pod shows 2 GPU nodes).
   - Qwen3-32B serving: headless `Service` + `StatefulSet` `vllm-worker` (replicas 4, `fantasy.com/gpu: 2` each), container args:
     `exec /root/miniconda3/bin/vllm serve /media/models/vllm/Qwen3-32B --served-model-name server-node1 --tensor-parallel-size 2 --dtype float16 --enforce-eager --gpu-memory-utilization 0.95 --max-model-len 32000 --max-num-seqs 8 --enable-force-include-usage --enable-prompt-tokens-details --host 0.0.0.0 --port 8000`
     Model mounted via `hostPath: /home/test/models → /media/models/vllm` (readOnly), `HF_HUB_OFFLINE=1` env. Verify 4 Running pods in namespace `vllm`, then hit the vLLM HTTP API inside the cluster.

## Pitfalls

- **1 card = 2 GPU nodes.** Don't be surprised if `fantgpu-smi` or `fantasy.com/gpu` counts double the physical card count.
- **Installer runs from its own directory** — `bash ./fantgpu-...run` and keep the file (needed for method-1 uninstall).
- **Reboot required** after driver install or the SMI/node count check will fail.
- **Expect exactly 5 `install Success` prints**; anything else = failed install, contact vendor support (low support budget in the field; the doc repeatedly defers to 技术支持).
- **GPU node count below expectations** on `fantgpu-smi` = problem to escalate, not a config fix.
- **CRI runtime mismatch** — choose docker or containerd consistently; the runtime configure + image import commands differ (`docker load` vs `ctr -n=k8s.io images import`). The import gadget for cloud plugins is `find ... | xargs -I {} <loader> -i {}`.
- **`127.0.1.1 hostname` / host resolution** can bite cross-node like other TGU boxes — unrelated to FTUCA but common in this fleet.
- **Cluster examples are debug-only** — production needs real network/HA tuning per the vendor 云原生参考手册; K8s install itself is documented in 《GR308S_MAX_云原生参考手册.pdf》, not this guide.

## Verification

```bash
fantgpu-smi
```
Confirms the stack is installed and every physical card reports the expected **2 GPU nodes**. In a cluster, additionally confirm `kubectl describe nodes | grep Capacity -A15` shows `fantasy.com/gpu` matching 2×card-count per node drilled down to the node's actual population.
