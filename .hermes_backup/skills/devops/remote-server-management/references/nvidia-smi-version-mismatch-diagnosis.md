# nvidia-smi Version Mismatch Diagnosis & Repair

**Session:** 2026-06-24 — 70.92 nvidia-smi version vs driver version mismatch

## Symptom

`nvidia-smi --version` shows mismatched version fields:

```
NVIDIA-SMI version  : 580.159.03   ← wrong/old
NVML version        : 595.71       ← correct
DRIVER version      : 595.71.05    ← correct (authoritative)
```

## Root Cause

The `/usr/bin/nvidia-smi` binary was **overwritten/replaced** with a copy from an older driver (580 series), even though the installed `nvidia-utils-595` package is at the correct 595.71.05 version. The string `580.159.03` is hardcoded in the binary itself — you can confirm with:

```bash
strings /usr/bin/nvidia-smi | grep -E '^[0-9]+\.[0-9]+\.[0-9]+'
# Output: 580.159.03  (matches the OLD version string)
```

## Diagnosis

### 1. Check if the binary is the original from the package

```bash
dpkg --verify nvidia-utils-595
```

- **No output** = binary is original, clean ✅
- `??5??????   /usr/bin/nvidia-smi` = **MD5 checksum mismatch** — the file has been modified/replaced ⚠️

The `5` flag in `dpkg --verify` output means the MD5 checksum differs from the expected value recorded in the package database.

### 2. Compare with a known-correct server

On a server with the same driver version where all three fields match:

```bash
# Compare binary stats
md5sum /usr/bin/nvidia-smi
stat --format='%s %y' /usr/bin/nvidia-smi
strings /usr/bin/nvidia-smi | grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | sort -u
```

If the MD5 differs between supposedly identical packages, the binary was tampered with.

### 3. Check for duplicate binaries in PATH

```bash
which -a nvidia-smi
```

If `/usr/local/bin/nvidia-smi` exists (and `/usr/local/bin` is before `/usr/bin` in PATH), it shadows the real one — this is a known pattern from WarpDrive xplatform stubs.

## Fix

### Fix 1: Reinstall the package (preferred)

```bash
sudo apt-get install --reinstall -y nvidia-utils-595
```

This restores the original binary from the .deb package. **No reboot required, no GPU downtime.** The vLLM server continues running.

### Fix 2: Manual swap (if reinstall doesn't help)

Copy the binary from a working server with the same driver version:

```bash
# On working server (e.g., 70.98):
scp /usr/bin/nvidia-smi user@10.10.70.92:/tmp/nvidia-smi

# On broken server:
sudo mv /usr/bin/nvidia-smi /usr/bin/nvidia-smi.bak
sudo mv /tmp/nvidia-smi /usr/bin/nvidia-smi
```

## Root Causes (What Replaced the Binary)

Possible origins of the stale binary:
1. **Overwritten by a CUDA toolkit install** — the CUDA toolkit bundle (`cuda-toolkit-13-0` or `cuda-toolkit-13-2`) ships its own `nvidia-smi` and may overwrite `/usr/bin/nvidia-smi` during package install if the package script doesn't check for existing versions
2. **Manual copy from another server** — someone copied the binary from a 580-series server (70.88) for compatibility testing
3. **apt-get install version conflict** — if `nvidia-utils-580` was installed before `nvidia-utils-595`, and the transition wasn't clean

## Prevention

After any driver/CUDA toolkit downgrade or upgrade, verify the SMI binary integrity:

```bash
dpkg --verify nvidia-utils-595
nvidia-smi --version
```

All three version fields should match (or at least NVML ↔ DRIVER should be close).

## When to NOT Worry

If `dpkg --verify` is clean and all three fields match, the slight version discrepancy between `NVIDIA-SMI version` and the other two fields is just a compile-time embedded string that the developer didn't update. As long as:
- `DRIVER version` matches the kernel module (always authoritative)
- `NVML version` is close to the driver version
- All nvidia-smi queries return valid results
- GPU workloads run normally

...there is no functional issue.
