# 192.168.12.12 Network Bottleneck & NAS-Based Transfer (2026-07-18)

## The Bottleneck

Measured with `iperf3 -c 192.168.12.12 -t 10` from 10.10.70.96:

```
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  11.6 MBytes  9.70 Mbits/sec  980
```

**9.7 Mbps with 980 retransmissions** — heavy packet loss, collapsed congestion window.

**Path:** 70.96 (ens20f0, 1GbE) → 10.10.70.254 (gateway) → 192.168.12.254 → 12.12 (br0, enp93s0f0, 1GbE).

Despite both ends reporting 1GbE Full Duplex, actual throughput is <10 Mbps due to gateway congestion or misconfiguration. This affects:
- SSH throughput: ~700 KB/s (regardless of cipher)
- rsync through SSH: ~500 KB/s–2 MB/s
- NFS writes to NAS from 12.12: ~1 MB/s (via same gateway)

## Workaround: Shared NAS Intermediary

Both 70.96 and 12.12 mount the **same NAS** (10.10.80.223):
- 70.96: `/mnt/nas_h100` (NFSv3, custom mount)
- 12.12: `/h100_nas` (NFSv4.2, rsize=1048576, pre-mounted)

### Transfer Pattern: source → NAS → target

**Phase 1: 70.96 → NAS (local write, no network)**
```
rsync -avP --info=progress2 /data/models/SOURCE/ /mnt/nas_h100/transfer_dir/
```
Effective speed: ~400 MB/s (limited by source disk read performance). 433GB completes in ~12 min.

**Phase 2: Symlink on 12.12 (instant)**
```
ln -s /h100_nas/transfer_dir /home/public/models/TARGET_NAME
```

NAS read speed from 12.12: **2.0 GB/s** (dd measured). The NFS mount uses `rsize=1048576,wsize=1048576,vers=4.2` — much faster than write.

### Phase 2 Alternative: Local Copy for Isolated Storage

If a real local copy is needed (not symlink), the NAS→12.12-local copy also goes through the gateway and will be slow (~1 MB/s). Options:
1. **Start it in background** via `setsid`:
   ```bash
   ssh 192.168.12.12 "setsid rsync -a /h100_nas/transfer_dir/ /home/public/models/TARGET/ > /tmp/copy.log 2>&1 &"
   ```
   Expect ~1 MB/s for ~5 days for 433GB — **impractical**.
2. **Fix the gateway congestion** (out of scope for remote debug).
3. **Live with the symlink** — NAS read speed is excellent from 12.12.

## Discovery Procedure

When diagnosing slow transfers to 12.12:

1. **Check raw TCP speed** (not SSH):
   ```bash
   iperf3 -c 192.168.12.12 -t 10   # from 70.96
   ```
   If <100 Mbps, the network path is the bottleneck.

2. **Check route:**
   ```bash
   ip route get 192.168.12.12       # from 70.96
   ```
   The route goes via 10.10.70.254 (gateway), not through the high-speed bond0 network.

3. **Verify 12.12's high-speed NICs are down:**
   ```bash
   ssh 192.168.12.12 "ip link show enp90s0f0np0"  # NO-CARRIER
   ```

4. **Test NAS speeds on both ends:**
   - 70.96 write to NAS: `dd if=/dev/zero bs=1M count=100 of=/mnt/nas_h100/test`
   - 12.12 read from NAS: `dd if=/h100_nas/test bs=1M count=100 of=/dev/null`
   - NAS speeds make 12.12's gateway the clear bottleneck.

## Related

- See `references/multi-hop-rsync-70-88-to-70-92.md` for the classic multi-hop rsync approach (direct A→B copy when servers can reach each other).
- See `internal-gpu-node-12-12` skill for 12.12's hardware/vLLM details.
