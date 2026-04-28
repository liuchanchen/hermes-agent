---
name: cron-job-troubleshooting
description: "Cron job常见问题排查：delivery设置、工具集配置、静默失败原因"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cron, troubleshooting, hermes]
---

# Cron Job 故障排查

## 常见问题

### 1. 定时任务没发送结果给用户
**原因**：`deliver` 设置为 `"local"` 而不是 `"origin"`

**解决方案**：
```python
cronjob(action='update', job_id='xxx', deliver='origin')
```

`deliver` 可选值：
- `"origin"` — 发送到用户的原始渠道（WeChat/Telegram等）
- `"local"` — 仅保存到本地文件，不发送

### 2. 工具在 cron job 中不可用
**原因**：cron job 使用受限的工具集，默认只有 `hermes-cli`，不包含 `browser`、`car-scraper` 等

**解决方案**：
- 使用 cron job 兼容的工具（terminal、file、web等）
- 或通过 script 参数运行独立脚本

### 3. 静默失败返回 `[SILENT]`
**原因**：
- 缺少必要工具（browser、car-scraper 等不在工具集中）
- 任务执行时间过长导致超时或被截断
- agent 输出中包含 `[SILENT]` 字样（触发抑制逻辑）

**排查步骤**：
1. 检查 cron job 的 `last_error` 字段
2. **主要手段**：查看 `~/.hermes/sessions/session_cron_<job_id>_<timestamp>.json` — 这是完整执行记录，比 `~/.hermes/logs/agent.log` 更可靠（日志可能被轮转或截断）
3. 确认所需工具在 cron job 工具集中可用

**Session 文件命名规律**：
```
session_cron_<job_id>_<YYYYMMDD_HHMMSS>.json
```
可以用 `ls -la ~/.hermes/sessions/ | grep cron_<job_id>` 快速找到。

### 5. 定时任务没有运行
**检查命令**：
```bash
cronjob(action='list')
```

确认：
- `enabled: true`
- `state: "scheduled"`
- `next_run_at` 时间正确

### 5b. 任务执行成功但微信推送失败（last_status: ok, last_delivery_error 有值）

**症状**：任务执行了，但微信没收到推送。日志有：
```
Timeout context manager should be used inside a task
Weixin send failed: Timeout context manager should be used inside a task
```

**原因**：`aiohttp 3.13.x` 的 `ClientSession.__aenter__` 在进入时调用 `asyncio.timeout`（`BaseTimerContext`），要求当前线程有运行中的 asyncio task。但 cron delivery 通过 `asyncio.run_coroutine_threadsafe` 调用 live adapter 时，协程虽然被调度成 task，却没有 "running task" context（task 运行在 ThreadPoolExecutor 线程，而非主线程）。

**特征**：`last_status: ok`（任务执行成功）+ `last_delivery_error` 有值（推送失败）。

**临时修复**：把 `deliver` 改为 `"local"`，阻止微信推送：
```python
cronjob(action='update', job_id='xxx', deliver='local')
```

**长期修复**：需修改 Hermes Agent 代码，让 WeChat 推送不走 `run_coroutine_threadsafe` 路径，而是用独立事件循环或修复 aiohttp 调用方式。

### 5. 手动触发测试
```python
cronjob(action='run', job_id='xxx')
```

**注意**：`cronjob(action='run', ...)` 不会创建新的 cron session，而是在**当前会话**中同步执行。真正的 cron session 文件名格式为 `session_cron_<job_id>_<timestamp>.json`，如果看不到新的这类文件，说明 run 在当前会话中执行了。

## 查看 cron 输出
```bash
ls -la ~/.hermes/cron/output/<job_id>/
cat ~/.hermes/cron/output/<job_id>/<timestamp>.md
```

## 查看 cron session
```bash
ls -la ~/.hermes/sessions/ | grep cron
```

## 快速修复命令
```python
# 修复 delivery
cronjob(action='update', job_id='xxx', deliver='origin')

# 暂停任务
cronjob(action='pause', job_id='xxx')

# 恢复任务
cronjob(action='resume', job_id='xxx')

# 立即运行
cronjob(action='run', job_id='xxx')
```