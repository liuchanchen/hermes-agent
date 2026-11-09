# Verifying whether a model filesystem is mounted over NFS-RDMA

When asked "is /modelzoo (or any model store) mounted by RDMA?", the mount options alone are NOT conclusive — check the config AND the actual kernel transport state in layers.

## Step 1 — mount options (config-level RDMA)

```bash
findmnt /modelzoo
# proto=rdma + port=20049 (NFS-RDMA port; TCP NFS uses 2049) => configured for RDMA
# rsize/wsize=1048576 (1 MiB) is typical of RDMA mounts
grep modelzoo /etc/fstab    # fstab may say proto=rdma too
```

## Step 2 — client kernel modules (RDMA support loaded)

```bash
lsmod | grep -E "rpcrdma|xprtrdma"
# rpcrdma = NFS-RDMA client impl, xprtrdma = transport. Both loaded => capable.
cat /proc/fs/nfsfs/servers   # per-server table
cat /proc/fs/nfsfs/volumes   # per-mount proto (root may be needed for full detail)
```

## Step 3 — RDMA hardware present

```bash
ls /sys/class/infiniband/    # e.g. mlx5_0, mlx5_bond_0 (ConnectX)
ibstat | head -20            # CA type / link state
```

## Critical caveat — config says RDMA ≠ bytes flow over RDMA

`proto=rdma` in mount options does NOT guarantee RDMA is the active transport. If the IB link is down (`ibstat` shows `State: Down / Physical state: Disabled` on the mlx5 device), the kernel NFS client can silently fall back to TCP while the mount keeps working. This is exactly what happened on 10.10.70.107 (oemp107): `/modelzoo` showed `proto=rdma,port=20049` and `rpcrdma/xprtrdma` loaded, but `mlx5_0` was Down.

To confirm the ACTUAL transport you need root to read `/proc/net/rpc/nfs` (xprt lines show per-transport counters) or run `nfsstat`. From an unprivileged user you cannot be 100% sure — say so honestly and offer the root check.

## Extra pitfall — NFS export source can change

On 70.107 the `/modelzoo` export source changed between sessions (was `10.10.68.71:/data`, at one point an empty export appeared). If a model dir "goes missing", re-run `findmnt /modelzoo` before assuming deletion — the mount may have switched to a different (possibly empty) export.

## Reference data point (70.107, 2026-08-25)

- `/modelzoo` = `10.10.68.71:/data`, nfs4, vers=4.2, `proto=rdma`, `port=20049`, 1 MiB rsize/wsize, `clientaddr=10.10.68.107`.
- Models present: deepseekv4-flash-0731, deepseekv4_flash, deepseekv4_pro, deepseekv4_pro_0813, Kimi-K3, MiniMaxAI, Qwen3.x.
- `df /modelzoo` = 14T total / 8.6T avail (35%).
- Access to 70.107 is password-only via the 70.96 jump host: `ssh jianliu@10.10.70.96 "sshpass -p '!QAZ2wsx' ssh ... jianliu@10.10.70.107 'cmd'"` — complex commands need a script staged via 96 then scp'd to 107.
