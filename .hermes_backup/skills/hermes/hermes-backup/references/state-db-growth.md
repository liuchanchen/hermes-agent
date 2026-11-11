# state.db Growth Tracking

The Hermes state database (`~/.hermes/state.db`) grows over time as conversation history accumulates. This file tracks its growth trend to anticipate when it may exceed GitHub's 100MB file limit.

## Measurement History

| Date | Raw Size | Gzip Size | Compression Ratio | Notes |
|------|----------|-----------|-------------------|-------|
| 2026-06 | ~511 MB (raw) | ~174 MB (gzip) | ~34% | First noted as exceeding 100MB limit; raw size estimated from compressor behavior |
| 2026-07-05 | 506,892,288 (483 MB) | 186,251,765 (178 MB) | 36.7% | 12 MB gzip growth in ~1 month vs June |
| 2026-07-06 | 511,078,400 (487 MB) | 187,863,740 (179 MB) | 36.8% | +4.2 MB raw / +1.5 MB gzip in 1 day — daily growth accelerating |
| 2026-11-11 | 662,577,152 (632 MB) | 246,597,589 (235 MB) | 37.2% | +145 MB raw / +59 MB gzip in ~4 months ⇒ ~1.2 MB raw/day, ~0.5 MB gzip/day (slower than the July spike) |

## Observations

- **Daily growth rate (observed)**: ~1.2 MB raw / ~0.5 MB gzip per day averaged over Jun–Nov 2026
- **Monthly growth rate (projected)**: ~36 MB raw / ~15 MB gzip per month
- The July 2026 spike (~4 MB raw/day) did not persist; long-run average is closer to 1.2 MB/day
- Compression consistently achieves ~36-37% of raw size (gzip level 6)
- Already exceeds GitHub's 100MB limit — must never be committed to git

## Timing (measured 2026-11-11, 632 MB raw)

- `sqlite3.backup()` snapshot + gzip + integrity_check: **43 s** total on this host
- gzip level 6 is the default in the skill script; level 1 would be ~2x faster at ~45% ratio (not worth it here)
- Disk headroom needed: raw copy + gz simultaneously ≈ 900 MB for a 632 MB db

## Backup Implications

- state.db.gz is ALWAYS excluded from git via `.gitignore`
- The `.gz` file is retained locally for restore purposes only (~235 MB as of 2026-11)
- Always run `pragma integrity_check` on the snapshot **before** deleting the raw copy (the skill script does this)
- Verify the gz round-trips to a valid sqlite header: `gzip.open(gz,'rb').read(16) == b'SQLite format 3\x00'`
- If state.db.gz ever needs to be removed from git history, use:
  ```
  git filter-repo --invert-paths --path .hermes_backup/databases/state.db.gz --force
  git remote add origin git@github.com:liuchanchen/hermes-agent.git
  git push origin +main:main
  ```
