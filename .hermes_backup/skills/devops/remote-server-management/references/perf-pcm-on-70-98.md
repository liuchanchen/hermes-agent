# Perf & Intel PCM on 70.98

Installed 2026-06-25 on 10.10.70.98 (Xeon Gold 6530, Emerald Rapids).

## perf

```bash
sudo apt-get install -y linux-tools-6.8.0-111-generic linux-tools-generic
# Result: perf version 6.8.12 at /usr/bin/perf
```

## Intel PCM

apt package `pcm` (202201-1) fails with:
```
Error: unsupported processor. CPU model number: 207
```
The old version doesn't know Emerald Rapids (GOLD 6530).

### Build from source

```bash
# Download from GitHub (curl works even when git clone times out from China)
curl -sL "https://github.com/intel/pcm/archive/refs/heads/master.tar.gz" -o /tmp/pcm.tar.gz
cd /tmp && tar xzf pcm.tar.gz && cd pcm-master

mkdir build && cd build
cmake ..                    # warns about missing googletest and old OpenSSL, non-critical
make -j$(nproc)             # builds pcm, pcm-memory, pcm-core, pcm-power, etc.
sudo make install           # /usr/local/bin/pcm*
```

Key binaries at `/usr/local/sbin/`:
- `pcm` — real-time CPU core counters
- `pcm-memory` — per-channel memory bandwidth
- `pcm-core` — per-core IPC/cache metrics
- `pcm-power` — package/DRAM power
- `pcm-numa` — NUMA-local traffic
- `pcm-msr` — raw MSR access
- `pcm-client` — at `/usr/local/bin/`

Note: `sudo` required for MSR access. Non-root run shows `Access to Processor Counter Monitor has denied (no MSR or PCI CFG space access).`
