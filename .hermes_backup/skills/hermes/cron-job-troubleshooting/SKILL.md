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

### 4. 任务执行失败——模型不存在（404 / Non-retryable client error）

**症状**：cron job 的 `last_status: error`，用户没收到推送。session 文件中**只有1条 user 消息**，agent 未生成任何回复。日志中有：
```
Non-retryable client error: Error code: 404 - {error: {message: 'The model \`xxx\` does not exist.'}}
```

**原因**：cron job 创建时固定了 model 名称（如 `data/code/my_models/SomeModel`），但 API 服务重启后该模型名不再可用。

**排查步骤**：
```bash
# 1. 查看 cron job 的模型配置
cronjob(action='list')  # 看 model 字段

# 2. 确认当前 API 可用的模型
curl -s <base_url>/v1/models -H "Authorization: Bearer <api_key>" 2>/dev/null

# 3. 检查 agent.log 确认错误
grep "Non-retryable client error\|model.*does not exist" ~/.hermes/logs/agent.log
```

**解决方案**：更新 cron job 的 model 为当前可用的模型名，或清空 model 以使用默认模型：
```python
# 方案A：指定一个存在的模型
cronjob(action='update', job_id='xxx', model='deepseekv4-flash', provider='custom')

# 方案B：清空 model（使用 config.yaml 中的默认模型）
# 注意：cronjob update 需要显式传 model，不能直接清空
```

**预防**：创建 cron job 时尽量不固定 model 名称，或使用稳定的模型别名。API 服务升级/重启后如模型名变化，需同步更新所有 cron job 的 model 字段。

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

**通用排查**：
1. 用户的最后状态检查：`cronjob(action='list')` → 看 `last_status` 和 `last_delivery_error`
2. 查看 cron 输出（不会被 delivery 失败影响）：`ls -la ~/.hermes/cron/output/<job_id>/ && cat ~/.hermes/cron/output/<job_id>/<timestamp>`
3. 查看完整 session 日志：`ls -la ~/.hermes/sessions/ | grep cron_<job_id>` → grep session JSON
4. 查看 agent.log：`grep "delivery\|weixin\|send failed\|ret=\|error" ~/.hermes/logs/agent.log | tail -20`

#### 类型 A：aiohttp Timeout

**日志特征**：
```
Timeout context manager should be used inside a task
Weixin send failed: Timeout context manager should be used inside a task
```

**原因**：`aiohttp 3.13.x` 的 `ClientSession.__aenter__` 在进入时调用 `asyncio.timeout`（`BaseTimerContext`），要求当前线程有运行中的 asyncio task。但 cron delivery 通过 `asyncio.run_coroutine_threadsafe` 调用 live adapter 时，协程虽然被调度成 task，却没有 "running task" context（task 运行在 ThreadPoolExecutor 线程，而非主线程）。

**临时修复**：把 `deliver` 改为 `"local"`，阻止微信推送：
```python
cronjob(action='update', job_id='xxx', deliver='local')
```

**长期修复**：需修改 Hermes Agent 代码，让 WeChat 推送不走 `run_coroutine_threadsafe` 路径，而是用独立事件循环或修复 aiohttp 调用方式。

#### 类型 B：iLink ret=-2 unknown error

**日志特征**：
```
WARNING [Weixin] ret=-2 unknown error; retrying without context_token
WARNING [Weixin] send chunk failed attempt=2/3, retrying in 2.00s: iLink sendmessage error: ret=-2 errcode=None errmsg=unknown error
ERROR   [Weixin] send failed: iLink sendmessage error: ret=-2 errcode=None errmsg=unknown error
```

**原因**：微信桥接接口（iLink）的临时性通信错误。前几次 retry 会尝试 `send with context_token` → 失败后 fallback 到 `send without context_token` → 同样失败。属于微信桥端的瞬时故障（连接抖动、超时或 token 过期），非 agent 本身问题。

**特征**：
- `last_status: ok`（任务执行成功）
- `last_delivery_error` 里有 `ret=-2`
- 通常是**偶发性的**，后续自动恢复
- 数据仍然可以通过 cron output 查看：`cat ~/.hermes/cron/output/<job_id>/<timestamp>.md`

**处理方法**：
1. **不要手动重启 gateway** — 发送失败不会影响后续消息，gateway 连接通常会自动恢复
2. **检查 gateway 是否在线**：看 agent.log 确认 `✓ weixin connected`
3. **数据恢复**：通过 cron output 读取已生成的报告，在用户询问时直接提供内容
4. **如果频繁出现**（连续 3+ 天），考虑：更换交付方式（如 deliver='local' + 定时推摘要），或排查 iLink 稳定性

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