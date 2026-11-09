# Docker Image Transfer Between GPU Servers (session 2026-08-20)

## Lesson 1: Target may ALREADY have the image (retag, don't transfer)

Before any `docker save` / transfer, **compare image IDs between source and target**.
The target often already holds the identical image under a registry-prefixed tag
(e.g. `10.10.91.56/sw2/...`). Same SHA256 image ID = same layers — just retag locally,
zero network transfer:

```bash
# Source ID
ssh SRC 'docker image inspect IMG --format "{{.Id}}"'
# Target: search for registry-prefixed variants
ssh DST 'docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | grep -i KEY'
# If IDs match → instant retag, done:
ssh DST 'docker tag REGISTRY/IMG DST_TAG'
```

Verified 2026-08-20: `vllm/vllm-openai:v0.25.0-flashinfer0614-local` on 92 was already
present on 98 as `10.10.91.56/sw2/vllm/vllm-openai:v0.25.0-flashinfer0614-local`
(identical ID `09876487e95a`) — retagged instead of transferring 8.8GB. This check also
tells you which registry-prefixed tags a node already pulls from.

## Lesson 2: `docker save | pigz` output file stays ~0 bytes for ~40s — don't abort

pigz buffers compressed output in memory before flushing to disk, so the output file
appears stuck at ~10 bytes for the first ~40 seconds of a large save. Verify it's alive
via `/proc/<pigz-pid>/io` (rchar/wchar climbing) or just wait — the file then grows
rapidly. Do NOT kill it thinking it's hung筋.

Verify the finished archive with `gzip -t` — takes minutes on multi-GB files; run it in
the background (`nohup ... &`) and poll for a result file, don't block the foreground.

## Lesson 3: Benchmark supervisor scripts auto-restart killed vLLM containers

`docker stop` on a vLLM container launched by a benchmark harness (`run_*_validation_v16.sh`
owned by another user) does NOT stick — the supervisor scripts detect the exit and
re-create the container seconds later (same name, new Created timestamp, GPUs reloaded).
The container appears "Up 2 minutes" again and all 8 GPUs re-fill to ~22GB.

To FULLY stop a benchmark-managed server you must also kill the supervisor processes:
`run_*_validation_v16.sh`, `tee -a ...validation_runner.log`, `tail -f ...service.log`.
These are the parent PIDs (bench harness) — without killing them the container will keep
coming back. Check with `pgrep -af 'run_.*v16|validation_runner|service.log'` after the
stop to confirm nothing will resurrect it.

Always verify the stop actually held: `docker ps` (container still gone after 60s) +
`nvidia-smi --query-gpu=utilization.gpu,memory.used` (all GPUs back to ~15 MiB baseline).

## Lesson 4: Container Start Time — the "running again" signal

When asked "when did the server start", `docker inspect --format '{{.State.StartedAt}}'`
gives the truth (times are UTC; add 8h for CST). If a container you *just stopped* shows
a fresh StartedAt minutes later, that's the auto-restart signal from Lesson 3 — the
harness brought it back. `FinishedAt` = `0001-01-01T00:00:00Z` (zero value) means it is
currently running (not stopped).
