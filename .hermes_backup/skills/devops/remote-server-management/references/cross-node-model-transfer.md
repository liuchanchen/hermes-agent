# Cross-Node Large Model Transfer

Patterns for transferring large model files (100GB+) between servers in the
10.10.70.x and 192.168.12.x networks, where direct inter-node links may be
bottlenecked.

## Network Topology

```
70.96 (8x RTX PRO 6000)      12.12 (8x H100 80GB)
      |                              |
      |  ens20f0 (1GbE mgmt)         |  br0 (1GbE)
      |  via 10.10.70.254           |  via 192.168.12.254
      |                              |
      +--- 10.10.80.223 (NAS) ------+
```

Both 70.96 and 12.12 mount the same NAS share from `10.10.80.223:/volume1/h100`:
- 70.96: `/mnt/nas_h100/` (NFSv3)
- 12.12: `/h100_nas/` (NFSv4.2)

## Measured Speeds

| Path | Speed | Notes |
|------|-------|-------|
| 70.96 → NAS (write) | 36-600 MB/s | Local to NFS, varies with NFS cache |
| 12.12 → NAS (read, cached) | 3.2 GB/s | First ~100MB from buffer cache |
| 12.12 → NAS (read, sustained) | ~1 MB/s | Through gateway bottleneck |
| 70.96 ↔ 12.12 (direct, raw TCP) | 9.7 Mbps | iPerf3 confirmed: 980 retransmits/10s |
| 70.96 ↔ 12.12 (SSH) | ~700 KB/s | Additional SSH encryption overhead |

**Key finding:** The gateway `192.168.12.254` / `10.10.70.254` between the two
subnets has a ~10 Mbps bottleneck with severe packet loss. Direct transfers
between 70.96 and 12.12 are impractical for large models.

## Recommended Transfer Strategy: NAS Intermediary

For copying models between 70.96 and 12.12:

### Step 1: Upload to NAS from source node (70.96)

```bash
# From 70.96, copy to NAS (fast — 36-600 MB/s)
rsync -avP --info=progress2 /data/models/SOURCE_MODEL/ /mnt/nas_h100/glm_transfer/
```

### Step 2: Download from NAS to destination node (12.12)

On 12.12, use `screen -dmS` to keep the copy alive across SSH disconnects. This is critical when routing through a jump host — nested SSH kills background processes (`nohup` and `setsid` are NOT sufficient through double SSH; `screen` is reliable):

```bash
# Kill any stale rsync processes first
pkill -9 rsync 2>/dev/null
# Also kill any leftover screen sessions
screen -wipe 2>/dev/null
# Clean destination
rm -f /home/public/models/DEST_NAME
mkdir -p /home/public/models/DEST_NAME
# Launch in detached screen session (survives SSH disconnects)
screen -dmS glm_copy rsync -a --info=progress2 /h100_nas/glm_transfer/ /home/public/models/DEST_NAME/
```

**Monitor progress:**
```bash
screen -S glm_copy -X hardcopy /tmp/sc.txt && cat /tmp/sc.txt
```

**Check completion:**
```bash
du -sh /home/public/models/DEST_NAME/
ls /home/public/models/DEST_NAME/*.safetensors | wc -l
```

### Alternative: Symlink (fast but not a real copy)

When the user accepts a symlink, this is instant since both nodes access the
same NAS share:

```bash
rm -f /home/public/models/DEST_NAME
ln -s /h100_nas/glm_transfer /home/public/models/DEST_NAME
```

NAS read speed from 12.12 is 2+ GB/s (when cached), sufficient for model
loading. The user in this session explicitly requested a full local copy (no
symlinks).

## NFS Cache Behavior

- **Burst phase**: Initial read of a file hits NFS client cache. On
  12.12, this gives ~3.2 GB/s for the first ~100MB.
- **Sustained phase**: Once cache is exhausted, the real network
  throughput through the gateway bottleneck appears: ~1 MB/s.
- For a 433GB model: ~5 days sustained. The first 64GB went in ~3 min
  (cache burst), then dropped to ~1 MB/s steady state.
