# Skill Library Update: 2026-07-18

## Updated

### `devops/internal-gpu-node-12-12` → v0.5.0

**What changed:**
- Corrected SSH password from `0` → `qs@2024.local` (previous `0` was broken)
- Added SSH key bootstrap pattern (70.96 → 12.12 passwordless via authorized_keys)
- Added full hardware info: 8× H100 80GB, driver 580.95.05, vLLM v0.20.0
- Added GPU monitoring dashboard on port 8080 (data/snapshots/*.json)
- Added model inventory: `/home/public/models/` has 150+ model dirs, including Qwen3.5-397B, MiniMax M2.7, DeepSeek R1 variants
- Added GLM-5.2-NVFP4 copy-in-progress status with screen monitoring command
- Added network bottleneck note: 70.96↔12.12 only 10 Mbps, use shared NAS as intermediary
- Removed the previous stale entry about "no /data/models/ on 12.12" (incorrect — /mnt/data3/public/models/ exists)
- Secondary port 51653 documented as dead (connection reset)

### `devops/remote-server-management`

**What changed (2026-07-31):**
- **Discovered 10.10.70.90** (warp-Bumblebee-BI5284): 2× RTX PRO 6000 Blackwell SE (10de:2bb9), Xeon Platinum 8558P (48c, 260MB L3), 7TB NVMe, NCCL 2.30.7+cuda13.3, NVML mismatch (595.71.05 kernel vs 595.84 lib — reboot needed), jianliu password broken (use qs/!QAZ2wsx). Private registry 10.10.91.56 with WarpDrive vLLM images. Models: gemma-4-31B-it, Qwen3-32B, Qwen3.6-35B-A3B-FP8/NVFP4, Qwen3-8B at `/data/home/public/models/tgu01/`.
- Added 70.90 to Supported Servers table
- Added 70.90 column to Model Inventory with its local model paths
- Added 70.90 row to Known Server Configs (bare node, no vLLM running)
- Created `references/70-90-initial-setup.md` — full discovery details
- Created `devops/server-discovery-update` skill — procedural workflow for future server discovery rounds
- **2026-07-27:** 70.88 live check: Qwen3.6-35B-A3B-NVFP4 PD Disaggregation running
- **2026-07-23:** Added 10.10.70.99 (oem-99, WarpDrive TGU01-Pro)
- Added 70.99 column to Model Inventory

## Created

### `devops/update-node-12-12-password`

Password-change skill for 192.168.12.12. Covers the exact chpasswd command through sshpass via jump host, with pitfalls for shell-special characters and !QAZ2wsx history expansion.

## Not changed

The existing `remote-server-management` reference `nas-intermediary-transfer.md` covers the generic NAS-as-intermediary pattern. The new `cross-node-model-transfer.md` is a sibling focused specifically on the 70.96↔12.12 case with concrete bench numbers and the screen-rsync procedure. These are complementary.

---

## 2026-09-01 — Discovered 10.10.70.106 (oemp106)

- **Discovered 10.10.70.106** (oemp106): 8× RTX 6000D (10de:2bb9, Blackwell GB202, CC 12.0, 85,651 MiB each), driver 610.43.02 (open kernel module), Ubuntu 22.04.4 / kernel 5.15.0-190, Xeon Gold 6530 ×2 (128 threads, 1TB RAM), 98G root + 7T NVMe LVM `/home` (66G used), Docker 29.7.2 + nvidia-container-toolkit 1.20.0 (jianliu in docker+sudo groups, uid 1005), dual-homed 68-net (bond0 10.10.68.106/23, 2×25G LACP; ibs35 RDMA DOWN). **Directly SSH-reachable from WSL** (no jump host, unlike 107). jianliu/!QAZ2wsx verified; no ~/.ssh → no GitLab key; no proxy. /modelzoo = 10.10.68.79:/modelzoo (28T) — different NFS source than 107's.
- Added 70.106 to Supported Servers table
- Added 70.106 column to Model Inventory (all models NFS on /modelzoo) and updated inventory date to 2026-09-01
- Added 70.106 row to Known Server Configs: DSpark DS-V4-Flash container `dspark-v9-hybrid-fix6-180k` (xiaqing/qs) on port 8001, TP=8, dspark speculative ×5, kv fp8, max_model_len 262144
- Created `references/70-106-initial-setup.md` + standalone `devops/remote-server-70-106` skill

## 2026-09-03 — 70.88 status check: production K8s node (MiniMax M2.7-NVFP4)

- Live check: 70.88 is now an **RKE2 Kubernetes agent** (kubelet active; tgu01-pro DRA kubelet-plugin, tgu01-pro device-plugin, rdma-shared-dp in kube-system). Docker ps is EMPTY — workloads run under containerd/CRI (`sudo crictl ps`).
- **Production workload**: pod `minimax-m2-7-main-*` — `vllm-server` serving **MiniMax M2.7-NVFP4**, TP=8/EP=8, ~29GB/GPU on all 8 GPUs, util ~99% on 5/8, up since ~2026-08-27; llm-d EPP router pod `minimax-m2-7-production-router-epp-*` (endpoint `inference.warpdrive.com/model-id=minimax-m2-7-nvfp4`, pool=minimax-m2-7-production, engine port 8000, grpc-health 9003).
- Old Qwen3.6-35B PD Disaggregation (docker, ports 8100/8200) is GONE.
- New quirk: `/usr/local/bin/nvidia-smi` stub exits 113 (like 70.94) — use `/usr/bin/nvidia-smi`.
- Updated Supported Servers + Known Server Configs rows; 70.88 must be treated as PRODUCTION (no restarts without owner approval).
