# state.db Growth Tracking

The Hermes state database (`~/.hermes/state.db`) grows over time as conversation history accumulates. This file tracks its growth trend to anticipate when it may exceed GitHub's 100MB file limit.

## Measurement History

| Date | Raw Size | Gzip Size | Compression Ratio | Notes |
|------|----------|-----------|-------------------|-------|
| 2026-06 | ~511 MB (raw) | ~174 MB (gzip) | ~34% | First noted as exceeding 100MB limit; raw size estimated from compressor behavior |
| 2026-07-05 | 506,892,288 (483 MB) | 186,251,765 (178 MB) | 36.7% | 12 MB gzip growth in ~1 month vs June |
| 2026-07-06 | 511,078,400 (487 MB) | 187,863,740 (179 MB) | 36.8% | +4.2 MB raw / +1.5 MB gzip in 1 day — daily growth accelerating |

## Observations

- **Daily growth rate (observed)**: ~4 MB raw / ~1.5 MB gzip per day as of July 2026
- **Monthly growth rate (projected)**: ~45 MB raw / ~15 MB gzip per month at current rate
- Earlier measurement (June → July 5) suggested 10-15 MB/month gzip, but daily tracking now shows faster growth
- At current rate, state.db.gz will reach ~200 MB by late August 2026
- Compression consistently achieves ~36-37% of raw size
- Already exceeds GitHub's 100MB limit — must never be committed to git

## Backup Implications

- state.db.gz is ALWAYS excluded from git via `.gitignore`
- The `.gz` file is retained locally for restore purposes only
- If state.db.gz ever needs to be removed from git history, use:
  ```
  git filter-repo --invert-paths --path .hermes_backup/databases/state.db.gz --force
  git remote add origin git@github.com:liuchanchen/hermes-agent.git
  git push origin +main:main
  ```

## Note on Measurement Method

Raw size is measured by `sqlite3.backup()` then checking filesize before gzip. The gzip step uses `gzip.open()` with default compression level. Both methods are deterministic. The one-day jump from 507→511 MB raw is plausible — the state.db accumulates conversation history continuously, and daily backup frequency captures that growth precisely.
