---
name: hermes-backup-push
description: "备份 ~/.hermes 到代码目录 .hermes_backup/，然后 git commit + git push 到 GitHub。commit message 格式：'backup hermes YYYY-MM-DD'"
version: 1.0.0
platforms: [linux]
---

# Hermes 备份 Push

一键执行本地备份（memories + skills + cron + databases），然后推送到 GitHub。

## 前置条件

- `~/.hermes/` 可读
- 代码目录 `/home/jianliu/work/hermes-agent/` 是 git repo，remote 为 `origin`
- SSH key 配置好，`git@github.com` 可达（`ssh -T git@github.com` 验证）
- `.hermes_backup/` 在 git 追踪下（不是 `.gitignore` 覆盖）

## 一键执行

```bash
cd /home/jianliu/work/hermes-agent

# 0. 生成 commit message
DATE=$(date +%Y-%m-%d)
COMMIT_MSG="backup hermes $DATE"

# 1. 本地备份（memories + skills + cron + databases）
rsync -a --exclude='*.lock' ~/.hermes/memories/ .hermes_backup/memories/
rsync -a --exclude='.bundled_manifest' --exclude='.git' ~/.hermes/skills/ .hermes_backup/skills/

rm -rf .hermes_backup/cron
mkdir -p .hermes_backup/cron
cp ~/.hermes/cron/jobs.json .hermes_backup/cron/jobs.json
cp -r ~/.hermes/cron/output .hermes_backup/cron/output
cp ~/.hermes/cron/.tick.lock .hermes_backup/cron/.tick.lock 2>/dev/null

mkdir -p .hermes_backup/databases
sqlite3 ~/.hermes/state.db ".backup .hermes_backup/databases/state.db"
cp ~/.hermes/dongchedi_l90.db .hermes_backup/databases/dongchedi_l90.db
cp ~/.hermes/whatsapp/state.db .hermes_backup/databases/whatsapp_state.db 2>/dev/null
cp ~/.hermes/whatsapp/dongchedi_l90.db .hermes_backup/databases/whatsapp_dongchedi.db 2>/dev/null

# 写 MANIFEST
python3 - <<EOF
import json, datetime, os
m = {
    "backup_timestamp": datetime.datetime.now().isoformat(),
    "includes": ["memories", "skills", "cron", "databases"],
}
with open(".hermes_backup/MANIFEST.json", "w") as f:
    json.dump(m, f, indent=2)
EOF

# 2. git add + commit + push
git add .hermes_backup/
git commit -m "$COMMIT_MSG"
git push origin main

# 3. 验证
echo "Pushed commit:"
git log --oneline -1
echo "Remote HEAD:"
git log origin/main --oneline -1
echo "Sync status:"
git status -sb | head -1
```

## 验证清单（执行后检查）

```bash
# 本地已 push
git log --oneline -1
# 期望: "backup hermes 2026-04-26" 或对应日期

# Remote 已同步（无 ahead）
git status -sb | head -1
# 期望: "## main...origin/main"  （无 M/前缀表示无 ahead）

# GitHub API 确认
curl -s "https://api.github.com/repos/liuchanchen/hermes-agent/commits?per_page=1" | \
  python3 -c 'import sys,json; c=json.load(sys.stdin); print(c[0]["commit"]["message"])'
# 期望: "backup hermes YYYY-MM-DD"

# 关键文件在 GitHub 上
curl -s "https://api.github.com/repos/liuchanchen/hermes-agent/contents/.hermes_backup/MANIFEST.json?ref=main" | \
  python3 -c 'import sys,json; c=json.load(sys.stdin); print("MANIFEST on GitHub:", c["sha"][:8])'
```

## 数据库备份说明

| DB | 备份方法 | 原因 |
|----|----------|------|
| state.db | `sqlite3 .backup` | 对活跃 DB 做原子快照，WAL 数据也会 flush |
| dongchedi_l90.db | `cp` | 静态 DB，直接复制 |
| whatsapp_state.db | `cp` | 静态 DB，直接复制 |
| whatsapp_dongchedi.db | `cp` | 静态 DB，直接复制 |

## 注意事项

1. **先 backup 再 push** — 不能只 push，必须先确保本地 `.hermes_backup/` 是最新的
2. **state.db MD5 与源不匹配是正常的** — `sqlite3 .backup` 做的是时间点快照，不是实时镜像
3. **whatsapp db 备份失败不算错误** — whatsapp 目录可能不存在
4. **.gitignore 不会影响 .hermes_backup** — `hermes-*/*` 模式只匹配 `hermes-` 开头的目录，`.hermes_backup` 不受影响
5. **cron output 历史文件会被完整保存** — 每次 push 都会把新的 output 文件一起提交