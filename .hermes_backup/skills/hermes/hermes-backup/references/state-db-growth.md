# state.db Growth Tracking

The Hermes state database (`~/.hermes/state.db`) grows over time as conversation history accumulates. This file tracks its growth trend to anticipate when it may exceed GitHub's 100MB file limit.

## Measurement History

| Date | Raw Size | Gzip Size | Compression Ratio | Notes |
|------|----------|-----------|-------------------|-------|
| 2026-06 | ~174 MB (gzip) | 174 MB | — | First noted as exceeding 100MB limit |
| 2026-07-05 | 506,892,288 (483 MB) | 186,251,765 (178 MB) | 36.7% | 12 MB growth in ~1 month |

## Observations

- Growth rate: approximately 10-15 MB/month (gzip compressed)
- At current rate, state.db.gz will reach ~200 MB by end of 2026
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
