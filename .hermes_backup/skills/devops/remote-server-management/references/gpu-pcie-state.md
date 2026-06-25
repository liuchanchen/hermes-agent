# GPU PCIe State: 70.88 vs 70.92

**Session:** 2026-06-24 — PCIe Gen diagnostic session

## Key Finding: Negotiated Max Discrepancy

Both servers have **identical hardware capability**: Device Max = Gen 5, Host Max = Gen 5. But their **negotiated link ceiling** differs even at idle:

| Field | 70.88 | 70.92 |
|-------|-------|-------|
| GPU | RTX 5090 32GB (Device 2b85) | RTX 5090 32GB (Device 2b85) |
| Driver | 580.159.03 | 595.71.05 |
| Perf State (sampled) | P8 (idle) | P8 (idle) |
| Current Link | Gen 1 (ASPM idle) | Gen 1 (ASPM idle) |
| **Device Max** | **Gen 5** | **Gen 5** |
| **Host Max** | **Gen 5** | **Gen 5** |
| **Negotiated Max** | **Gen 5** | **Gen 4** ← capped |

The `Max` field (negotiated ceiling) is recorded independently of the current link speed. 70.92's link is capped at Gen 4 — this is a real configuration difference, not an idle artifact.

## Root Cause Analysis (Unconfirmed — Requires Further Investigation)

Possible causes (ordered by likelihood):

1. **BIOS PCIe Speed Policy** (most likely) — 70.92 BIOS may be set to "PCIe 4.0" or "Gen 4 Only" instead of "Auto/Gen 5". Check via IPMI/physical access.
2. **Driver version** — 595.71.05 vs 580.159.03: newer driver may use more conservative Gen 5 training.
3. **PCIe signal integrity** — Gen 5 (32 GT/s) is sensitive to PCB trace; 70.92's riser/switch may not reliably train to Gen 5.

## Per-Server PCIe State (Verified 2026-06-24)

Both servers: all 8 GPUs sampled, all identical within each server.

### 70.88 — RTX 5090 ×8, Driver 580.159.03
```
GPU Link Info
    PCIe Generation
        Max              : 5       ← negotiated ceiling (Gen 5)
        Current          : 1       ← idle ASPM
        Device Current   : 1
        Device Max       : 5       ← hardware capability
        Host Max         : 5
    Link Width
        Max              : 16x
        Current          : 16x
    Performance State   : P8
```

### 70.92 — RTX 5090 ×8, Driver 595.71.05
```
GPU Link Info
    PCIe Generation
        Max              : 4       ← negotiated ceiling (Gen 4) — CAPPED
        Current          : 1       ← idle ASPM
        Device Current   : 1
        Device Max       : 5       ← hardware capability
        Host Max         : 5
    Link Width
        Max              : 16x
        Current          : 16x
    Performance State   : P8
```

## Verified nvidia-smi Commands

```bash
# Structured detail (all fields, includes GPU Link Info block)
nvidia-smi -q -i 0

# GPU Link Info section only
nvidia-smi -q -i 0 | sed -n '/GPU Link Info/,/Bridge Chip/p'
nvidia-smi -q -i 0 | grep -A 20 'GPU Link Info'

# All 8 GPUs, concise
for i in 0 1 2 3 4 5 6 7; do
  echo "=== GPU $i ==="
  nvidia-smi -q -i $i | grep -E 'PCIe Gen|Link Width|Perf'
done

# CSV: gen current, gen max, width
nvidia-smi --query-gpu=index,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current --format=csv,noheader

# grep raw Device Max / Host Max
nvidia-smi -q -i 0 | grep -E 'Device Max|Host Max|Max.*:'

# WRONG syntax (do not use):
nvidia-smi pcie             # unrecognized option
nvidia-smi -d pcie         # -d takes display types (MEMORY/UTILIZATION/...), not 'pcie'
nvidia-smi -q -i N -d pcie # -q and -d are mutually exclusive
```

## lspci GPU Bus Addresses

Both servers: identical bus topology.

| GPU | Bus ID |
|-----|--------|
| 0 | 16:00.0 |
| 1 | 27:00.0 |
| 2 | 38:00.0 |
| 3 | (via bridge 48:03.0 — no direct GPU device) |
| 4 | 5a:00.0 |
| 5 | 98:00.0 |
| 6 | a8:00.0 |
| 7 | b8:00.0 |

**Note:** `lspci -s 16:00.0` on WarpDrive servers shows "WarpDrive Technology" or "Device 2123:0180" (PCIe switch/riser vendor/device ID), while nvidia-smi shows "NVIDIA Corporation Device 2b85" (actual GPU device ID). This is normal for GPU servers with riser cards — nvidia-smi reads the actual GPU device ID, lspci reads the bus endpoint which reflects the riser/switch. Always use `nvidia-smi -L` and `nvidia-smi -q` for GPU identification.

**WarpDrive servers lspci vs nvidia-smi device ID mapping:**

| Server | lspci device (GPU slot) | nvidia-smi GPU | Notes |
|--------|------------------------|---------------|-------|
| 70.92 | 16:00.0 WarpDrive 0180 | NVIDIA RTX 5090 | Same bus, different ID source |
| 70.93 | 16:00.0 Device 2123:0180 | NVIDIA RTX 5090 | Same pattern |
| 70.94 | 16:00.0 WarpDrive 0180 | NVIDIA RTX 5090 | Same pattern |

## Interpretation

- **Gen 1 at idle** = normal ASPM power-saving, not a fault
- **Device Max = Gen 5 on RTX 5090** = nvidia-smi reports Gen 5 capability despite RTX 5090 spec sheet saying Gen 4 — use nvidia-smi value as ground truth
- **Negotiated Max = Gen 4 on 70.92** = real cap requiring BIOS/driver/signal investigation