# NAS Intermediary Pattern: Cross-Server Model Transfer

**Date:** 2026-07-18
**Model:** glm_5_2_nvfp4 (~433 GB, 47 safetensors shards)
**Source:** 10.10.70.96:/data/models/glm_5_2_nvfp4/
**Destination:** 192.168.12.12:/home/public/models/glm5_2_nvfp4/

## The Problem: Direct SSH is 10 Mbps

The direct link between 70.96 (10.10.70.x) and 12.12 (192.168.12.x) routes through a gateway that bottlenecks at **~10 Mbps with heavy packet loss**:

```text
$ iperf3 -c 192.168.12.12 -t 10
[  5]   0.00-10.00  sec  11.6 MBytes  9.70 Mbits/sec  980 retries
```

At this rate, 433 GB would take **~5 days** via direct SSH/rsync. Changing SSH ciphers (`aes128-ctr`, `chacha20-poly1305`) did not help — the bottleneck is network-level, not encryption.

## The Solution: Shared NAS as Intermediary

Both servers mount the **same NFS share** from `10.10.80.223:/volume1/h100/` — discovered this is the fast path.

| Server | NAS Mount Point | Write Speed | Read Speed |
|--------|----------------|-------------|------------|
| 70.96  | `/mnt/nas_h100/` | 36 MB/s (dd) | 3.2 GB/s (NFS cache) |
| 12.12  | `/h100_nas/` | — | 2.0 GB/s (cached) → 1 MB/s (sustained past cache) |

### Phase 1: Source → NAS (fast)

```bash
# On source server (70.96), copy to its NAS mount:
rsync -avP --info=progress2 /data/models/glm_5_2_nvfp4/ /mnt/nas_h100/glm_transfer/
```

- Achieved **400+ MB/s** average (local ext4 → NFS)
- 433 GB completed in ~12 minutes

### Phase 2: NAS → Destination

If direct SSH from source to destination is slow, the NAS→destination copy may also be slow when the link to the NAS routes through the same bottlenecked gateway. Two options:

**Option A: Symlink (instant, no throughput penalty)**

```bash
# On destination:
ln -s /h100_nas/glm_transfer /home/public/models/glm5_2_nvfp4
```

No disk usage on destination's local storage. vLLM can load the model directly from NAS — NFS read speed is sufficient for model loading (serial reads at 2+ GB/s).

**Option B: Full local copy (via screen/systemd-run)**

```bash
# On destination, via screen to survive SSH disconnects:
screen -dmS glm_copy rsync -a --info=progress2 /h100_nas/glm_transfer/ /home/public/models/glm5_2_nvfp4/
```

Speed may be slow (~1 MB/s) if route to NAS is bottlenecked. Monitor with:
```bash
screen -S glm_copy -X hardcopy /tmp/sc.txt
cat /tmp/sc.txt | grep -a "MB/s\|kB/s"
du -sh /home/public/models/glm5_2_nvfp4/
```

## Using `screen` for Persistent Remote Processes

When SSH is run through a jump host or ProxyJump, background processes (`nohup`, `&`, `disown`) are killed when the SSH connection closes. `screen` keeps processes alive:

```bash
# Launch on remote:
screen -dmS <session_name> <command>

# Check if session exists:
screen -ls | grep <session_name>

# View output:
screen -S <session_name> -X hardcopy /tmp/sc.txt
cat /tmp/sc.txt

# Reattach:
screen -r <session_name>
```

## SSH Key Setup for Cross-Server Access

```bash
# On source server (e.g., 70.96):
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub

# On destination (e.g., 12.12):
echo "<pubkey>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Test:
ssh -o StrictHostKeyChecking=no <user>@<dest-ip> "hostname"
```

Key auth avoids `sshpass` overhead during rsync.

## Network Diagnostics Toolbox

When direct transfers are slower than expected:

1. **Check negotiated link speed:** `cat /sys/class/net/<iface>/speed`
2. **Measure raw TCP throughput:** use iPerf3 (install if needed)
3. **Check for packet loss:** iPerf3 retransmit count
4. **Find shared infrastructure:** NFS mounts, common storage, NAS
5. **Check routing:** `ip route get <dest-ip>` shows which interface/gateway is used

## Key Lessons

1. **Gigabit link speed ≠ throughput.** The enp93s0f0 reported "1000Mb/s" with `ethtool`, but actual iPerf3 was 9.7 Mbps. Always measure with iPerf3.
2. **NAS is the universal intermediary.** If servers A and B both mount the same NAS, use it as a fast staging area — avoids server-to-server network bottlenecks.
3. **Symlink is instant.** If a model is already on shared storage, a symlink avoids a multi-hour copy with no inference performance penalty.
4. **`screen` survives SSH disconnects** through a jump host. `nohup` does not — it dies when the parent SSH session closes.
5. **Stale background processes compete.** Multiple partial rsync/cp processes writing to the same destination thrash the disk. Kill all before restarting.
6. **`500MB burst + 1MB/s sustained`** = NFS client cache exhausted. The initial fast speed is local RAM buffering data. Once that fills, the actual network throughput determines the rate.
