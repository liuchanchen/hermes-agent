# Cron Health Check Session Pattern (2026-06-25)

## Session Summary

The cron health check agent ran on 2026-06-25 08:00 CST. The pre-run script reported:
- 7 total tasks
- 6 NEED-RESEND (all iLink Weixin rate limited)
- 1 HEALTHY (每日做梦精炼)

The agent processed all 6 NEED-RESEND by consolidating their content into the final auto-delivered response, as individual sends would all hit the 30s iLink cooldown.

## Key Discovery: Output File Structure in Cron Jobs

Cron job output files at `~/.hermes/cron/output/<jid>/<timestamp>.md` have a specific structure:

1. **Lines 1-N**: The full cron job prompt, including the entire SKILL.md content embedded by the cron system. This can be 50-550 lines depending on the skill size.
2. **Line after `## Response`**: The actual report content produced by the job.

This structure makes reading these files expensive — the skill prompt can be 15-20KB while the actual report is only 2-4KB. To efficiently extract the report:

```python
# Read from the end of the file, not the beginning
with open(path, 'r') as f:
    lines = f.readlines()
# Find the report start
for i, line in enumerate(reversed(lines)):
    if '## Response' in line:
        report_start = len(lines) - i
        break
report = ''.join(lines[report_start:])
```

## iLink Rate Limiting Details

| Detail | Value |
|--------|-------|
| Error message | `iLink sendmessage rate limited; cooldown active for 30.0s` |
| Cooldown duration | 30 seconds per channel |
| Typical failure cascade | All 6 WeChat-delivery jobs fail together |
| Mitigation | Consolidate into one auto-delivered report |
| Not a persistent failure | Jobs succeed when retried individually |

## Affected Job IDs in This Run

| Job ID | Name | Status |
|--------|------|--------|
| 7c1e45b92026 | 懂车帝乐道L90监控 | NEED-RESEND |
| a964294ed664 | 每日财经早报 | NEED-RESEND |
| 89f4554bce6e | Hermes备份+GitHub Push | NEED-RESEND |
| 4f84b0c63dc2 | 每周二入职提醒 | NEED-RESEND |
| abbcf2686299 | 每日面试提醒 | NEED-RESEND |
| 13fbed6a9ac6 | Cron健康检查&自动恢复 | NEED-RESEND |
| 1b38a660ab9a | 每日做梦精炼 | HEALTHY |
