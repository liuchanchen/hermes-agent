---
name: gpu-cluster-monitor
version: 1.0.0
description: Operate the GPU monitor dashboard and probe fleet GPUs.
tags: [gpu, monitoring, 70.x, dashboard]
---

# GPU Cluster Monitor (agentless, stdlib)

Tool: /home/jianliu/work/gpu-monitor — real-time per-GPU dashboard for the 17-node
fleet (124 GPUs: 66/87/88/90/92/93/94/95/96/97/98/99/103/106/107/108 at 10.10.68.x
+ 192.168.12.12). Agentless SSH collection; nothing installed on GPU nodes. Full ops
details in its README.md; this skill holds the operating procedures.

## When to Use

- "start/stop/restart the GPU monitor" · "check the fleet" · "is the monitor up"
- Adding/removing a node from the dashboard
- Debugging a node showing offline/stale in the UI
- Any GPU-count or auth drift on 68.87 / 68.99 / 68.103 / 68.106 / 68.108 / 12.12

## How to Run

```bash
# WSL dev instance is now a systemd USER service (2026-09-04) — preferred over nohup:
systemctl --user status|restart|stop gpu-monitor.service
systemctl --user disable gpu-monitor.service        # to stop auto-start at login
journalctl --user -u gpu-monitor.service -n 50      # logs
```

Manual/probe commands (for 68.88 deployment or debugging):

```bash
cd /home/jianliu/work/gpu-monitor
python3 -m backend.main --once                        # one-shot fleet probe -> JSON
python3 -m tests.test_parsers && python3 -m tests.test_idle   # unit tests
pkill -f 'backend.main --port 8787'                    # stop (manual runs only)
nohup python3 -u -m backend.main --port 8787 > /tmp/gpu-monitor.log 2>&1 &   # daemon start
# ON 68.88 (since 0923): do NOT nohup — use `systemctl --user restart gpu-monitor.service` (liujian, linger enabled)
```

- **Run with miniconda python** (`/home/jianliu/miniconda3/bin/python`), NOT
  `/usr/bin/python3` — system python lacks pexpect, so password-auth collectors fail
  at import time (service crash-loop; exit 1 with ModuleNotFoundError in journal).
- WSL service file: `~/.config/systemd/user/gpu-monitor.service` (Restart=always,
  WorkingDirectory=/home/jianliu/work/gpu-monitor). NOTE: WSL systemd user services
  survive only while the WSL VM runs; they die with `wsl --shutdown`.
- **2026-09-04 outage root cause**: the old nohup-launched backend died silently
  (~12:47, no OOM/crash log — likely killed with its parent session), so the web page
  froze on stale data. Fixes shipped: (1) backend now runs under systemd user service
  with auto-restart; (2) frontend polling is ALWAYS on alongside SSE (was: an
  `if (!lastSnap)` gate meant polling never started once SSE had delivered once, so
  a dead backend left the page frozen forever); (3) stale-banner (index.html +
  markStaleBanner in app.js) shows "⚠ 数据已过期 N 分钟" when the newest node
  reading is >3 min old; (4) server.py SSE writes are serialized per-client with a
  lock — the handler keepalive thread and the broadcaster thread previously wrote
  the same socket unsynchronized, corrupting SSE frames.

Verify: `curl -s http://127.0.0.1:8787/api/health` — expect per-node status+GPU counts.

## Shared deployment on 68.88 (systemd user service since 2026-09-23)

Production instance runs ON 68.88 for team access: **http://10.10.68.88:8787**. Since 2026-09-23 it runs as a **systemd USER service** (`loginctl enable-linger liujian` done via qs sudo — survives logout/boot):
- Unit: `~/.config/systemd/user/gpu-monitor.service` (Restart=always, `Environment=GPU_MON_CONFIG=%h/gpu-monitor/nodes-88.yaml`)
- Manage: `systemctl --user status|restart|stop gpu-monitor.service` (as liujian@88) — **replaces the old pkill/nohup procedure**
- Code at `~/gpu-monitor/` (= `/home/liujian/gpu-monitor` after the 0923 home migration), config `nodes-88.yaml` (backup `.bak-0923`), log `run.log` (systemd append).
- **ExecStart MUST be `/usr/bin/python3`** — 88's `~/miniconda3` is a broken half-copy (pip shebangs → `/home/warp/miniconda3`, no pexpect/yaml); system python HAS pexpect+yaml for liujian (verified 0923).
- **GOTCHA (cost an hour on 0923): the backend loads `$GPU_MON_CONFIG` else `nodes.yaml`** — the old nohup launch exported GPU_MON_CONFIG=nodes-88.yaml; without that env the service silently loads `nodes.yaml` (13 different entries) and per-node fixes to `nodes-88.yaml` do nothing. The unit now sets the env.
- Auth (0923 domain migration): 88's pubkey (`/home/liujian/.ssh/id_rsa.pub`, comment jianliu@oem88) installed into `liujian@` on 87/88/90/92/93/94/95/96/97/98/99/103/108 — those entries are `auth: key` + `user: liujian`. 106 auth:key user:liujian; 107 password liujian; 66 auth:key; 12.12 password. **10.10.68.87 not yet in the config.**
- 88 self-monitored via `auth: local` — its card shows `local rc=18` (NVML driver/library mismatch, userspace 580.178 vs kernel 580.173) until the host is rebooted; 94 same (`ssh rc=18`). Owner-approved reboots needed; the monitor itself is fine.
- WSL dev instance may also run on localhost:8787 — keep only one if SSH load matters.

## Idle highlight (15-min unused feature, ZERO-USAGE memory semantics, 2026-09-04)

GPU flagged `idle: true` when used memory stayed at/below 64 MiB
(IDLE_MEM_FREE_MAX_MB in poller.py) for the ENTIRE past 15 min (window 900 s, needs
≥5 min sample span + ≥3 samples after restart — no false idles on boot).
Zero-usage semantics: nothing allocated in the window = nobody used the GPU.
A GPU that merely HOLDS memory (vLLM worker on 29 GB) is NOT idle — it occupies the
GPU. (History: v1 util≤5% → v2 memory-unchanged ±16MiB → v3 zero-usage, per user.)
UI: blue outline + 💤Nm tag (N = minutes unused). Fields: `gpus[].idle`,
`gpus[].idle_since_min`. Tests: tests/test_idle.py (8 tests).

## Card header field (changed 2026-09-07)

Card top-right shows the node's LATEST SAMPLE TIME (HH:MM:SS from `n.ts`, 24h) —
user request: sample duration (latency_ms) was unhelpful clutter. Drawer subtitle
matches: "… · 最后采样 HH:MM:SS". latency_ms is still in the API payload if needed.
IMPORTANT: 88's deployed app.js had drifted from the repo (repo had the newer
stale-banner/SSE changes; 88 didn't, and vice versa). Always diff 88's file
against the repo BEFORE patching, apply the change to BOTH, and push with a
.bak backup. Frontend is static — no restart needed after app.js push.

## GPU process USER attribution (added 2026-09-07, option A live)

Each processes[] entry has `user` (container/pod name), `image`, `runtime_s`.
Data path: /proc/<pid>/cgroup -> runtime id -> deployed /tmp/.gm_who2.sh
(docker inspect OR sudo crictl inspect; prints id|name|image per id). The script
is auto-deployed on demand via base64 (`_ensure_who`); sudo pw argv only for
auth:local 88 (`sudo -S`); 93/95/98 use passwordless `sudo -n crictl`.
Identity = container/pod name (e.g. PD_nvidia_prefill, dsv4-flash-vision-exp-*).
All compute runs as root inside containers (loginuid unset) — uid is useless.

Pitfalls fixed (do not regress):
- nentry tuple = (name, img, ts): stale check MUST index [2] for ts — [1] is the
  image string → `float - str` TypeError → node offline (96, 2026-09-07)
- _who_lookup returns {full_id: (name, img)} — unpack info[0], info[1]
- pexpect wrapper expands $vars and mangles quotes → build remote cmds via xargs
  and base64-deployed scripts; never inline $vars or nested quotes
- docker ps gives 12-char ids vs 64-char cgroup ids → prefix match
- ps fallback: `ps -o pid=,user=,etimes=` also fills runtime_s (⏱ tag on UI)

**107 attribution gap fixed (2026-09-20)**: 107's containers are docker-run and
liujian lacks the docker group — WHO2's unprivileged `docker inspect` failed and
crictl cannot see docker containers at all, so 107's cards fell back to uid
"root" forever. WHO2 gained a `sudo -S docker inspect` fallback (uses the account
password), and `_who_lookup` now passes the password for local AND password auth
nodes. 107 resolves PD_nvidia_prefill_tp1; the first sample after a backend
restart may still say root (who2 cache warms on the second poll).

## Card header field (changed 2026-09-07)

Symptom: some/all password-auth nodes (90/93/99/106/107) show `stale` with ts
frozen hours/days ago, while key-auth nodes keep updating. run.log shows their
last success then only 66/12.12 fail lines.

Root cause chain: pexpect.spawn (pty.fork) from a poller thread while ANOTHER
thread holds the sqlite mutex → the forked child (still python, pre-exec) runs
threading teardown at fork and deadlocks on the ghost sqlite lock → child never
execs ssh, stays alive holding pty+db fds → parent poller thread blocks forever
in child.expect. Evidence: N single-thread python children of the main proc,
1:1 timestamps with each node's last-success ts, all stuck in
sqlite3VdbeFinalize/futex (gdb via sudo), db fds + /dev/ptmx open, no ssh child.

Fix deployed 2026-09-07 (two layers, both in repo + on 88):
1. Fork-safety guard: `collectors._fork_guard` RLock — pexpect.spawn waits on it;
   poller threads take `collectors.fork_lock_guard()` around store writes +
   latest-registry updates, so pty.fork() can never race a sqlite-lock holder.
2. Watchdog (poller.py `_stuck_child_watchdog`, 60s period): kills our python
   children that are single-threaded + hold ptmx fds + age >120s (never exec'd
   ssh = fork-deadlock signature); logs `[watchdog] killed stuck fork child`.
   Real ssh children (exe=/usr/bin/ssh) are never touched.
Deployed by full restart (old 7-proc tree killed). Verified: all 11 reachable
nodes live, only real-ssh children present, watchdog 0 kills (clean start).
Note: `--once` mode can take >4 min when 12.12/66 hang their full timeouts.

Prevention idea (not yet implemented): use `start_new_session=True` subprocess
sshpass-style or a lock-ordered store write before spawning pexpect; at minimum
add a watchdog that kills single-thread python children holding ptmx.

## SSH-auth/slow-session triage for password nodes (2026-09-15)

Symptom in run.log/health: password-auth node shows `timeout waiting for command
marker` — THREE different root causes share this error; triage with a raw pexpect
stage dump (sendline pw, expect [\$,#,Permission denied,password:,TIMEOUT], print
child.before):
1. **Wrong password** → buffer shows `Permission denied, please try again`.
   Old code misreported this as marker-timeout (expect list order: Permission
   denied matched as idx 2 before `password:` could). Fixed in _pexpect_exec:
   use child.match_index (2=denied, 3=reprompt) → raises `ssh password rejected`;
   idx 4 → `no shell prompt after auth (slow session)`.
2. **Slow session** (12.12: login shell prompt takes 40–120s — 25 users, slow PAM;
   load average is LOW ~4, it is NOT load) → prompt-wait was fixed 10s, command
   got sent before shell ready and was swallowed. Fix: prompt timeout now
   `max(10, min(timeout-15, 90))`. A 12.12 `echo OK` probe takes ~40s end-to-end.
3. **Command genuinely slow/hung** → marker never comes; check with manual probe.

Auth-drift incidents 0915: 106 jianliu acct removed (use liujian/985202Qs~, same
as 107 — nodes.yaml updated); 66 jianliu pw `!QAZ2wsx` rejected (host key changed
= reimaged; WSL key auth still works, 6×A100; 88's pubkey installed into 66's
authorized_keys so 88-instance can use auth:key — nodes-88.yaml push pending user
approval).

## 106 flapping/offline: sssd/PAM auth stalls (2026-09-15, fixed)

Symptom: 106 repeatedly vanished from both dashboards; health showed `no shell
prompt after auth (slow session or dead sshd)` mixed with `ssh auth failed (code 3)`.

Root cause chain (raw pexpect stage dump + one ssh diag batch):
1. 106 auths via **sssd** (sssd_pam/sssd_be). pam_sss intermittently STALLS —
   bimodal latency: instant success (~0.5s) vs 45s+ hang, streaks of 3-4
   consecutive stalls. Some stalls end with sshd closing the connection right
   after the password packet (`Connection closed by ... port 22`) — looks like a
   dead node but isn't; retry on a FRESH connection succeeds instantly.
2. Monitor config made it worse: 106 had default `timeout_s: 25` → prompt-wait
   capped at **10s** (any stall >10s failed), and BOTH instances polled it every
   5s (0.4 auth/s of sshd+sssd load — an auth storm).
3. Box was slammed by an unrelated user: `rg` at 1193% CPU for 2h+ (VS Code
   remote search, 10.9 GB RSS node server) + admin restarting sshd/sssd 3× while
   fighting the same congestion. GPU-side truly idle (0 MiB/0% all 8).

Fixes (repo + 88 deployed, WSL + 88 instances restarted):
1. `collectors._pexpect_exec`: fresh-connection RETRY, up to 3 attempts 2s apart,
   only on transient classes listed in `_TRANSIENT_AUTH_ERRORS` (stage-1
   timeout/EOF, prompt-timeout after pw, connection dropped after pw). Never
   retries `ssh password rejected` or marker-timeout (command already ran).
   After-password expect list now includes pexpect.EOF (match_index 5) so drops
   raise a clean RuntimeError instead of leaking pexpect.EOF.
2. 106 in nodes.yaml AND nodes-88.yaml: `interval_s: 30`, `timeout_s: 90`
   (prompt-wait 75s rides out stalls). Label no longer claims idle.
3. nodes-88.yaml 66 entry now `auth: key` in the repo too (0915 auth-drift fix
   synced from 88's deployed copy).

**Drift lesson (extends the app.js rule)**: the repo's nodes-88.yaml had silently
lost two deployed changes (66 key-auth, 106 liujian creds) — 88's copy was newer.
ALWAYS `diff` deployed-vs-repo for EVERY file you push (backend + yaml, not just
frontend), back up with `.bak-<date>`, push only after reconciling.

**keep-last-good (poller, 2026-09-15)**: a failed poll no longer overwrites
`latest[host]` when the previous reading is live/stale — before this, ONE sssd
stall wiped the card to "no GPU data" + red error for minutes until the next
poll (~2-5 min cycle) succeeded. Kept stale samples stay honest via the ts in
the card header and the 数据已过期 banner; failures still go to the store
history. `stale` must count as keep-worthy, else the first failure after the
stale threshold (3×interval) wipes the sample anyway. NOTE: after a backend
restart every card starts blank until its first poll completes (12.12: up to
~15-20 min worst case with 3×280s retries) — that is expected, not a bug.

## 106 ROOT CAUSE FOUND & FIXED with sudo (2026-09-15 14:46 CST)

liujian@106 has FULL sudo ((ALL:ALL) ALL, password = account pw, use `sudo -S`).
Root-level diagnosis nailed the stall chain:
1. `access_provider = ad` with NO `ad_gpo_access_control` → sssd default
   **enforcing** → EVERY login runs an online GPO check: gpo_child fetches GPOs
   over **SMB from the DC**. That SMB path drops: `copy_smb_file_to_gpo_cache
   failed [102] Network dropped connection on reset` → `GPO-based access control
   failed` → **login DENIED** → sshd closes right after the password packet =
   the exact `Connection closed by ... port 22` client signature. When the SMB
   path merely hangs, sssd_be gets killed by its own WATCHDOG (seen in journal)
   and PAM requests during recovery stall for 45s+ = the bimodal latency.
2. DNS was NOT the problem (SRV lookup 0.019s, DCs win-ad01/win-ad02 fine).
3. `/etc/hosts` typo: `127.0.1.1 oem106` vs hostname `oemp106` → "unable to
   resolve host" warnings (cosmetic but real bug).

Fixes applied (root, config backed up to `/etc/sssd/sssd.conf.bak-0915-gpofix`):
- `ad_gpo_access_control = disabled` in `[domain/warpdriveai.com]` — GPO SMB
  fetch no longer gates logins. Tradeoff: no GPO-based login restriction (fine
  for this compute fleet; revisit after the DC SMB path is repaired).
- `cached_auth_timeout = 3600` — password auths ride the cache for 1h.
- `/etc/hosts`: `127.0.1.1 oem106 oemp106`.
- sssd restarted (active, 0 GPO failures / 0 watchdog kills since).

**Measured post-fix: password auth 10/10 success, avg 1.0s, max 2.9s** (was
4-6/10 with 45s stalls + dropped connections). Key auth unchanged 6/6. Monitor
polls ~2.6s steady; one rc=255 blip during the sssd restart was masked by the
retry ladder + keep-last-good. If DC SMB is ever repaired and GPO enforcement
is wanted again: restore the backup, set `permissive` (never `enforcing` on a
compute node with this DC path).

**Key-auth switch for 106 (2026-09-15, resolves the stall surface)**: the stalls
live in the password-verification PAM path (pam_authenticate → sssd online
check; bimodal ~0.5s cache-hit vs 45s+ online-stall, sshd sometimes closes right
after the password packet). Installed WSL + 88 pubkeys into liujian@106
~/.ssh/authorized_keys (via base64-shipped script, idempotent grep-append) and
switched 106 to `auth: key` in nodes.yaml AND nodes-88.yaml (interval 10s then,
4s since the 0917 fleet cap; timeout_s stays 90). Measured: key-auth polls ~2.7s end-to-end vs 81s in
wedged password windows. REMAINING sssd dependency: pam_acct_mgmt/session phase
still consults sssd — can still stall occasionally (saw one TimeoutExpired);
`ssh_exec_key` now retries transient failures (TimeoutExpired, rc=255 w/ empty
stderr; deterministic rc like NVML rc=18 never retried), and keep-last-good
covers the UI. Full node-side cure (needs root on 106) — hand to the 106 admin:
(1) diagnose: /var/log/secure for the stalling PAM phase; sssd logs with
debug_level=6; `sssctl domain-status`; sssd version (2.x fixed many responder
hang bugs); (2) clean restart: stop sssd, rm /var/lib/sss/mc/* /var/lib/sss/db/*,
start (cache corruption class); (3) tune sssd.conf: cache_credentials=True +
cached_auth_timeout up, entry_cache_timeout up, and if AD set
ad_gpo_access_control=permissive (GPO check goes online EVERY login — classic
per-login stall); (4) check DC/LDAP health from 106 (time ldapsearch);
(5) systemd-logind/dbus health for the session phase; (6) kill the rg
full-disk search (user lixinwei's VS Code remote, 1193% CPU for hours).

## NVML driver/library mismatch (rc=18, 2026-09-15)

Symptom: `nvidia-smi` → `Failed to initialize NVML: Driver/library version
mismatch (NVML library version: X)`; ssh rc=18 (nvidia-smi exit code), collector
raises `ssh rc=18: ` with empty stderr. Hit 88 (NVML 580.178 vs kernel 580.173.02,
userspace upgraded 09-12) and 94 (NVML 610.57 vs kernel 595.84, upgraded 09-14).
Diagnose: `cat /proc/driver/nvidia/version` (kernel module ver) vs NVML lib line
in the error; `grep nvidia /var/log/dpkg.log | tail` shows upgrade date. Fix =
host reboot (or rmmod/modprobe nvidia when no process holds the driver) — needs
root/sudo; monitoring side can only report it. Do NOT reboot production 88 (vLLM
serving) without owner approval.

## Ops pitfalls

- **pkill self-match over SSH**: a remote one-liner containing the pattern
  `backend.main --port 8787` makes pkill kill its own sshd wrapper (exit 255, no
  restart). Restart pattern instead: just `setsid bash -c 'nohup python3 -u -m
  backend.main ... &'` when the old proc is already gone; or use a bracket pattern
  `backend[.]main` when killing from a shell whose own cmdline contains the string.
- **Never prefer the skill's pexpect-ssh.py helper over _pexpect_exec** in
  collectors.py: the helper swaps process-wide sys.stdout (races under concurrent
  collectors → empty fleet output), returns int rc on failure paths
  (`'int' has no attribute 'splitlines'`), and leaks raw SMI output into the server
  log. ssh_exec_blocking must always call the self-contained _pexpect_exec.
- **setsid+nohup over ssh may hang the client** even with </dev/null: run the start
  command in its own ssh call, expect occasional client timeout (exit 124) — verify
  with a SEPARATE ssh call (`ps -ef | grep backend[.]main | wc -l`).
- **Security-gated terminal calls**: repeated curl/urllib to `10.10.68.88` from WSL
  may trip approval gates — batch checks via one ssh call to 88 and read run.log
  locally on 88 instead.

## Architecture (1-paragraph)

One poller thread per node (nodes.yaml: collector/auth/interval_s/timeout_s) →
executes the node's own SMI over SSH (key=subprocess BatchMode, password=self-contained
pexpect in collectors.py) → normalized JSON → SQLite ring (7d) + SSE/REST (stdlib
ThreadingHTTPServer) → vanilla-JS grid UI. No external deps beyond PyYAML+pexpect.

## Collector quirks (verified 2026-09-04)

- nvidia nodes: ALWAYS `/usr/bin/nvidia-smi` (stub wrappers at /usr/local/bin exit 113 on
  88/94-style nodes). 11-field CSV layout, no timestamp field requested.
- wd-smi (68.93): supports nvidia-style `--query-gpu` CSV + `--query-compute-apps`.
  UUID prefix differs between queries (`TGU-…` vs `GPU-…`) — parser joins on guid core.
- warpdgpu-smi (68.99): NO query API — parse the fixed table (GPU-Util `X%(Y%)`,
  Memory-Usage `NMiB / NMiB`, Temp `NC`, Pwr `NW`). No process list available.
- 12.12: SSH takes minutes when loaded → interval_s=4, timeout_s=280, `stale_after_s: 360`,
  `cm: true` (ControlMaster fast path below makes warm polls ~1s, not minutes).

## Fleet drift alerts (check when counts look wrong)

- 68.99 re-imaged twice in one day (TGU01F ×2 → ×8 on 2026-09-04). Verify with
  `warpdgpu-smi | grep -c TGU01F` (via pexpect-ssh.py, password auth).
- 68.106: password auth WORKS, key auth broken. DSpark workload was removed 0904 (idle).
- 68.88 is PRODUCTION RKE2 (MiniMax) — read-only monitoring only, 4s interval (0917 cap).

## Interval cap: max interval < 5s (2026-09-17, user request)

Every node polls at 3s (default) or 4s; nothing above. New per-node knob
`stale_after_s` (backend/config.py Node + poller `_apply_stale_flags`): 0 = auto
`max(20, 3×interval)`; set explicitly for slow-EXEC nodes — 12.12 uses 360 so its
card doesn't flicker stale while a poll legitimately takes up to ~280s. Failure
backoff stays `min(30s, max(interval, 2**failures))` — a dead node retries at worst
every 30s, no auth storm (the 106 lesson). Both instances (WSL + 88) deploy the same
yaml; after a config/code push restart BOTH (`systemctl --user restart
gpu-monitor.service` locally; on 88 pkill `backend[.]main` + setsid nohup relaunch).

### ControlMaster fast path (`cm: true`, 2026-09-17)

interval_s is a FLOOR (sleep between serialized polls) — with cold logins at 40-120s+
(25 users, slow PAM), 12.12's card still refreshed only every ~6.6 min (measured
latency 395s). Fix: per-node `cm: true` → the backend keeps ONE authenticated
`ssh -N -o ControlMaster=yes` master per node (`_MASTERS` in collectors.py, auth via
pexpect ONCE — success signal is SILENCE in the post-password window, then `-O check`
must pass), and every poll is a subprocess client over the socket (command mode, no
PTY, no login shell): measured 0.036s/poll, full collect ~0.75-1.2s (2026-09-17).
Gotchas, learned the hard way: (1) interactive `ControlMaster=auto` spawns inside
pexpect DO NOT persist — child.close() kills the master and wedges the socket for
later clients (probe: 3×20s timeouts); the master must be a dedicated `-N` child the
backend owns. (2) Interactive mux sessions still run the remote login shell (slow);
command-mode clients do not — that is where the speed comes from. (3) After a backend
restart an orphaned master keeps serving — `_ensure_master` reuses it; a stale socket
FILE with no listener must be unlinked or `ControlMaster=yes` silently disables
multiplexing. (4) The master is an /usr/bin/ssh child, so the stuck-fork watchdog
never kills it. (5) When cleaning up, kill PPID-1 cold-ssh orphans — two 50h-old ones
were hanging around on 88 from the pre-fix era.

## Adding a node

1. Probe manually: try `/usr/bin/nvidia-smi --query-gpu=index,... --format=csv,noheader`,
   then `wd-smi ...`, then `warpdgpu-smi` — pick the matching collector.
2. Append to nodes.yaml **and nodes-88.yaml** (both instances run the same registry) with
   correct auth + interval_s/timeout_s.
3. `python3 -m backend.main --once` to verify parsing, then restart the server.

### Key auth for a domain node (worked example: 68.97, 2026-10-28)

Domain nodes authenticate as `liujian / 985202Qs~`; the monitor wants key auth. Install the
collector host's pubkey into the node's REAL home (`getent passwd liujian` → 97 is
`/home/ad/liujian`, NOT `/home/liujian`):

```bash
# from WSL, password auth via SSH_ASKPASS (see remote-server-management skill)
cat > /tmp/.ap.sh <<'EOF'
#!/bin/bash
echo '985202Qs~'
EOF
chmod 700 /tmp/.ap.sh
SSH_ASKPASS=/tmp/.ap.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 setsid -w \
  ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no \
      -o UserKnownHostsFile=/dev/null liujian@10.10.68.97 \
      "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys" < /tmp/88pub.txt
```

Get `/tmp/88pub.txt` with `ssh liujian@10.10.68.88 cat ~/.ssh/id_rsa.pub` (88 is the
collector host for the shared dashboard). Then verify **from 88**, not from WSL:
`ssh liujian@10.10.68.88 'ssh -o BatchMode=yes liujian@10.10.68.97 hostname'`.

### 68.97 (added 2026-10-28) — attribution without sudo/docker

`liujian` on 97 is NOT in sudoers and NOT in the docker/containerd group; `qs/!QAZ2wsx`
is rejected. So `sudo -n crictl` and `docker inspect` both fail, and WHO2 falls back to
`/var/log/containers/*<cid>*.log`. Two rules keep that working:

- the glob entries are SYMLINKS into 0700 `/var/log/pods` → guard with `[ -L ]`, `[ -e ]`
  returns false and the whole lookup silently yields nothing;
- WHO2 reads stdin with `while read -r id` and `_build_cg_cmd` feeds `/proc` reads via
  `xargs -I{}`, so ids/pids must be one per LINE (`printf '%s\n' …`). A space-separated
  list collapses to one bogus id → every card shows `root`/`pod-xxxxxxxx`. Both bugs were
  live fleet-wide until 2026-10-28; regression tests live in `tests/test_attribution.py`.

97 runs `deepseekv4-flash-1017` (pod `engine/deepseekv4-flash-1017-*`, TP=8, ~80.7 GB/GPU
resident, 0% util between requests). Key auth polls cost ~0.5 s idle / ~2 s full collect.

### 68.87 / 68.103 / 68.108 (added 2026-10-28)

Same recipe as 97 (domain account `liujian/985202Qs~`, home `/home/liujian` on all three,
key installed from BOTH WSL and 88). Facts that matter for labels/attribution:

- **68.87** `oem87` — RTX5090 ×8, K8s node, mostly idle (only user `xiayuhang`'s python on
  GPU7). No sudo/docker group → attribution falls back to the ps uid.
- **68.103** `oem103` — RTX5090 **×2** (not 8!), vLLM `VLLM::EngineCore` in docker
  (cgroup `docker-<id>.scope`), API on 127.0.0.1:8000. No sudo/docker group, and there is
  no `/var/log/containers/*<cid>*.log` for that docker id → shows `root`.
- **68.108** `oemp108` — RTX6000D ×8, vLLM `VLLM::Worker_TP*_EP*` (k8s) + two ComfyUI
  `python main.py --listen` procs (ports 8188/8788) running as user `panyiro`. No
  sudo/docker group; k8s pods resolve to `pod-<8hex>`/uid, docker/comfyui procs to the uid.

**10.10.68.104 (oemp104) is NOT monitored — no credentials work from WSL, 88, 106 or 108.**
Every account/password tried (`liujian`, `liuchao`, `qs`, `jianliu`, `root` ×
`985202Qs~`/`!QAZ2wsx`) is rejected; sshd only offers `publickey,password`; ports 9100 and
10250 are open but unauthenticated, 6443/80 are closed. From WSL the 22 banner is empty and
every port "accepts" then goes silent (looks like a NAT/edge artifact — from 88 the banner
is normal OpenSSH 8.9p1). The host belongs to the Kimi-K3 TP8×PP3 cluster (master at
`10.10.68.104:29501`, peers 105/106, docs in `~/work/tgu01-pro-model-deployment/kimi3` on
88) and its account is `liuchao` with key-only SSH — ask the owner for a key or a
read-only account before adding it.