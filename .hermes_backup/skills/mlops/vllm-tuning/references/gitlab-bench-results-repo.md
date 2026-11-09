# Retrieving benchmark results from the tgu01-pro GitLab repo

The `tgu01-pro-model-deployment` repo (all `vllm_bench_results/` benchmark JSONs,
`backend_results/`, per-model startup scripts) lives on a GitLab instance:

- Host: `gitlab.qs.com` = `10.10.50.23`
- Web/API access is AUTH-GATED: `/-/raw/` and `/-/blob/` URLs redirect to
  `/users/sign_in`, unauthenticated `/api/v4/projects?search=...` returns `[]`
  or `404 Project Not Found`. Do NOT fight the HTTP path.
- **SSH git access works** with existing config. `~/.ssh/config` already maps
  `gitlab.qs.com` → `10.10.50.23`, User `git`.
- Repo path over SSH: `git@gitlab.qs.com:tgu01-pro/tgu01-pro-model-deployment.git`

## Fast single-file / single-dir fetch (sparse + blob:none)

The repo is large (model startup scripts + many JSON result dirs). Do a blob-less,
sparse clone so only the needed dir is materialized:

```bash
cd /tmp && rm -rf bench_repo
timeout 120 git clone --depth 1 --filter=blob:none --sparse \
  "git@gitlab.qs.com:tgu01-pro/tgu01-pro-model-deployment.git" bench_repo
cd bench_repo
git sparse-checkout set "minimax_m3_nvfp4/vllm_bench_results/20260805_165815"
GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10" git checkout
ls minimax_m3_nvfp4/vllm_bench_results/20260805_165815/
```

Add another model's results later without re-cloning:

```bash
git sparse-checkout add "qwen3_235b/vllm_bench_results/fathomless_5090_2507_nvfp4_native202752_run1"
GIT_SSH_COMMAND="ssh -o BatchMode=yes" git checkout
```

## Enumerate what results exist

List all benchmark summary files without downloading blobs:

```bash
GIT_SSH_COMMAND="ssh -o BatchMode=yes" \
  git ls-tree -r --name-only HEAD | grep -iE "benchmark_summary\.(json|csv)$"
```

## benchmark_summary.json shape

Each run dir has `benchmark_summary.json` (array) plus one per-cache-ratio JSON
`<label>_2048in_500out_cache_{0,0p4,0p8}_<ts>.json`. Standard fields per entry:
`label`, `model_id`, `num_prompts`, `cache_hit_rate` (0.0/0.4/0.8),
`duration`, `completed`/`failed`, `total_token_throughput`, `request_throughput`,
`output_throughput`, plus percentile TTFT/TPOT/ITL/E2EL.

`total_token_throughput` = `(total_input_tokens + total_output_tokens) / duration`.
All runs in these dirs use 200 prompts, 2048-in/500-out, rate=inf, max_concurrency=64,
so throughput numbers are comparable across models; cache ratio is the sweep variable.

## Pitfalls

- Avoid a full `git clone` with blob filter + `git checkout` of everything — it
  auto-packs and can take >3 min for the tree; on a slow link prefer the sparse
  path above.
- A `git ls-tree` loop that shells out to `git show` per file to grep contents
  is slow and triggers security-scan approval; grep the summary model labels
  returned by `ls-tree` instead, then sparse-checkout ONLY the dirs of interest.
- Web SSO cookies / authenticate via the browser won't help the CLI; SSH is the
  supported read path here.
