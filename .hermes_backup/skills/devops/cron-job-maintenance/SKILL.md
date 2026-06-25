---
name: cron-job-maintenance
description: Monitor, repair, and resend Hermes cron jobs — process pre-run script output with NEED-RESEND/NEED-RERUN/HEALTHY tags, extract actual report content from output files, handle iLink Weixin rate limiting by consolidating deliveries, and produce health check reports.
version: 1.0.0
author: curator
license: MIT
platforms: [linux]
---

# Cron Job Maintenance

Umbrella skill for operating the Hermes cron health check and auto-recovery agent. This runs periodically as a cron job itself, inspecting the output of other cron jobs and handling delivery failures.

## When to Use

- When the pre-run script output is injected into context and contains `[NEED-RESEND]`, `[NEED-RERUN]`, or `[HEALTHY]` tagged entries
- When cron job delivery failed and content needs to be re-sent
- When a cron job needs to be re-executed due to failure
- When producing a consolidated health check report

## Pre-Run Script Output Format

The pre-run script injects structured data into context with the following format:

```
检查时间: YYYY-MM-DD HH:MM:SS CST
任务总数: N

[NEED-RESEND] [jid] Job Name
  error: delivery error: Weixin send failed: iLink sendmessage rate limited; cooldown active for 30.0s
  output (N chars):
[actual report content here, may be truncated at 2016 chars]

[NEED-RERUN] [jid] Job Name
  status=error, last_run=...

[HEALTHY] [jid] Job Name — last_run=...

---SUMMARY---
HEALTHY: N
NEED-RERUN: N
NEED-RESEND: N
RESEND jid|Name|WITH_CONTENT (or NO_CONTENT)
RERUN jid|Name
```

### Status Categories

| Tag | Meaning | Action |
|-----|---------|--------|
| `HEALTHY` | Ran successfully, no action needed | Skip |
| `NEED-RERUN` | Failed and should be re-executed | Call cronjob runner |
| `NEED-RESEND` | Ran successfully but delivery failed | Resend content |
| `WITH_CONTENT` | Report content is included in context output field | Extract and use directly |
| `NO_CONTENT` | No output content available | Skip, nothing to send |

## Processing NEED-RESEND Tasks

### Step 1: Check if content is in context
The pre-run script includes `output (N chars):` followed by the actual report. If the output says `WITH_CONTENT`, the report body is in the context (may be truncated at 2016 chars).

### Step 2: Check if content was truncated
Output in context is capped at ~2016 chars. If a report seems incomplete (ends mid-sentence), get the full output from the output file:

```bash
# Find the latest output file for a job ID
ls -t ~/.hermes/cron/output/<jid>/ | head -1
```

Then read the tail of the file — the actual report starts after the skill prompt content (usually around line 100+ for simple jobs, later for complex ones). The file structure is:
- Lines 1-~N: Skill prompt + instructions (can be very long, sometimes 400+ lines)
- Line ~N+: `## Response` followed by the actual report content

To get just the report:
```bash
# Find the end of the skill prompt content by searching for "## Response"
grep -n "## Response" ~/.hermes/cron/output/<jid>/<file>.md | tail -1
```

### Step 3: Handle iLink Weixin rate limiting
The iLink WeChat gateway enforces a 30-second cooldown between messages. When multiple tasks fail delivery simultaneously, independent sends will all fail with the same error. **The solution is consolidation** — embed all resend content into the agent's final response as one cohesive report, rather than attempting independent sends.

### Step 4: Compose the consolidated output
Since the final response is auto-delivered, include all resend content with clear section separators and numbered headers.

**Format:**
```
🔍 Cron 健康检查报告
━━━━━━━━━━━━━━━━━━━━━
检查时间: YYYY-MM-DD HH:MM CST

✅ 正常：N个（list names）
🔄 已自动恢复：N个（已整合全部重发内容到本报告）
❌ 仍失败：N个（list names + reason）

━━━━━━━━━━━━━━━━━━━━━

## 1️⃣ 🚗 懂车帝 乐道L90 二手车监控报告
[full report content]

━━━━━━━━━━━━━━━━━━━━━

## 2️⃣ 📊 每日财经早报
[full report content]

...etc
```

## Processing NEED-RERUN Tasks

For tasks tagged `NEED-RERUN`, the job ran but failed (usually API timeout, network error, or resource unavailable). Execute the job with the appropriate runner tool:

- For dongchedi-l90-watch: Use `dongchedi_watch` tool or the Python script via xvfb-run
- For dream pipeline: The cron system typically handles reruns automatically
- For other jobs: Check the specific skill/script path

After triggering, note the status in the final report.

## iLink Rate Limiting Pattern

The iLink WeChat gateway uses a per-session cooldown of 30 seconds. This means:

- **Single deliveries** always succeed (1 message per 30s is fine)
- **Bulk deliveries** fail predictably (multiple messages in same tick hit cooldown)
- **Health check consolidation** is the designed mitigation — the health check agent collects all failed deliveries into its own auto-delivered response
- The 6-resend-at-once pattern is expected (懂车帝L90, 财经早报, 备份报告, 入职提醒, 面试提醒, cron健康检查 all fail together)
- **Never retry individually** — they will all hit the same cooldown. Consolidate into one report.

## Cron Output File Locations

```
~/.hermes/cron/output/
├── <job-id-1>/           # e.g., 7c1e45b92026
│   ├── 2026-06-24_22-04-22.md   # Latest run output
│   └── ...                       # Historical outputs
├── <job-id-2>/           # e.g., a964294ed664
│   ├── 2026-06-23_08-02-08.md
│   └── ...
└── ...
```

Files are named as `YYYY-MM-DD_HH-MM-SS.md`. Find the latest by sorting with `ls -t`.

## Pitfalls

- **Output files are large (20KB+)** because they embed the full SKILL.md and prompt content. The actual report is in the last 50-150 lines. Don't read the whole file — read from offset -100 or search for `## Response`.
- **Don't send individual messages** when multiple NEED-RESEND tasks exist — they'll all hit the iLink 30s cooldown. Consolidate into the final response.
- **Don't use [SILENT]** on health check runs — the report must always be produced (health check is the delivery itself).
- **The context `output (N chars)` is truncated at 2016 chars**. Always verify by reading the full output file for reports that seem incomplete.
- **L90 dongchedi output files** include the entire skill prompt (~124 lines) before the report starts at line ~125 (after `## Response`).
- **财经早报 output files** have the actual report starting around line ~133 (after `## Response`).
- **入职提醒 output files** embed the interview skill (very long, ~536 lines of prompt before the report at line ~537).
- **面试提醒 output files** similarly embed the interview skill (report starts around line ~540).
- **备份报告 output files** are shorter (~50 lines of prompt before the report).
- **Cron健康检查 output files** contain the PREVIOUS health check run's output, not the current run — only use the context-provided content for these.

## Failure Modes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| All 6 jobs show NEED-RESEND with "rate limited" | iLink 30s cooldown | Consolidate into final response |
| Report ends mid-sentence in context | 2016 char truncation | Read full file from `~/.hermes/cron/output/` |
| Output file has skill prompt only, no report | Job didn't produce a result | Check job timing — the file may be a previous failed run |
| NEED-RERUN job won't start | Service (LLM API, browser) unavailable | Note in report; manual intervention needed |

## Verification Checklist

- [ ] All HEALTHY tasks confirmed as "正常" in report count
- [ ] All NEED-RESEND content extracted (from context or files)
- [ ] Consolidated report includes all resend sections with clear separators
- [ ] NEED-RERUN tasks have been attempted (if possible) and status noted
- [ ] Report format matches: status summary first, then individual sections
