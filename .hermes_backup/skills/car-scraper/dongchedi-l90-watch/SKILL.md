---
name: dongchedi-l90-watch
description: 懂车帝 乐道L90 二手车价格监控 cron job。每天自动抓取列表页和详情页，对比此前快照报告新增/下架/价格变动。
category: car-scraper
trigger: cron job (daily, usually 14:00 UTC)
---

# 懂车帝 乐道L90 监控

## 用途
监控懂车帝上乐道L90二手车的挂牌价格、车源数量变化，通过SQLite持久化历史数据。

## 脚本路径
- 主脚本: `~/work/hermes-agent/tools/dongchedi_l90_watch.py`
- 工具包装器: `~/work/hermes-agent/tools/dongchedi_tool.py`
- SQLite数据库: `~/work/hermes-agent/tools/dongchedi_l90.sqlite`

## 运行方式

### 方法1: 直接运行（带xvfb，因为无X server）

**必须先预热 profile！** 懂车帝反爬系统会拦截没有 browser session 的直接访问。详见下方"反爬处理"。

```bash
cd ~/work/hermes-agent/tools
xvfb-run python3 dongchedi_l90_watch.py \
  --list-url "https://www.dongchedi.com/usedcar/20,!1-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-918-25234-310000-1-x-x-x-x-x" \
  --db "dongchedi_l90.sqlite" \
  --max-details 30 \
  --profile-dir "/tmp/dongchedi_profile"
```

### 方法2: 通过 Hermes 工具
```python
dongchedi_watch(
  list_url="https://www.dongchedi.com/usedcar/...",
  max_details=30,
  headless=True
)
```

### 方法3: 手动验证（首次或验证码）
```bash
python3 dongchedi_l90_watch.py \
  --list-url "..." \
  --headed \
  --manual-verify-only
```

## 修复的 Bug
- `--headed` 默认值原来是 `True`，导致无X server环境启动headed浏览器失败。
- 已修复为 `default=False`（2026-05-15）。
- 工具包装器 (`dongchedi_tool.py`) 逻辑：headless=True时不传--headed；headless=False时传--headed。

## 输出格式
脚本输出JSON，包含：
- `matched_count`: 当前匹配车源数
- `new_count` / `removed_count` / `changed_count`: 相对于上次的变化
- `items`: 当前所有车源详情
- `delta.new / .removed / .changed`: 变化详情

## 注意
- 懂车帝可能有反爬验证，首次需要在headed模式下手动完成验证并保存profile
- profile目录: `~/.crawl4ai/profiles/dongchedi_profile`
- 每次运行会写入 `listings` 表（当前快照）和 `listings_history` 表（历史记录）
- 数据库 schema 无 `runs` 表 — 通过 `listings_history` 的 `fetched_at` 字段追踪历史

## 反爬处理（关键）

懂车帝使用 Tengine 反爬系统。关键问题：
1. **直接访问 used car 列表页 URL 返回空 body** — 没有 cookie/session 的请求被挡在 `<html><head></head><body></body></html>` 页面。
2. **普通 curl 请求也返回 `content-length: 0`** — 纯 HTTP 请求被直接拒绝。
3. **crawl4ai 的 `wait_for="css:body"` 超时** — 因为返回的 body 是空的，所以 body 选择器一直等待不到内容。

### 修复方案（2026-06-27 发现）

**必须先预热浏览器 profile 再运行脚本**，不能直接从零访问 used car 页面。

```python
# 预热 profile：先用 Playwright 访问 homepage 建立会话
import asyncio
from playwright.async_api import async_playwright

async def warm_profile(profile_dir: str):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            profile_dir,
            headless=False,  # xvfb-run 下运行
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            viewport_width=1920,
            viewport_height=1080,
        )
        page = await context.new_page()
        # 先访问 homepage 建立 cookies/session
        await page.goto('https://www.dongchedi.com', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(2)
        # 再访问 used car 页面预热列表页 cookie
        await page.goto('使用的车列表URL', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        await context.close()

asyncio.run(warm_profile('/tmp/dongchedi_profile'))
```

预热后，再用以下命令抓取（可以使用原来的 profile）：
```bash
xvfb-run -a python tools/dongchedi_l90_watch.py \
  --list-url "你的列表URL" \
  --db /tmp/dongchedi_l90_cron.db \
  --max-details 30 \
  --profile-dir /tmp/dongchedi_profile
```

### Cron job 完整流程

由于无持久 profile，每次 cron 执行需要：
1. 创建临时 profile 目录
2. 用 Playwright 预热（访问 homepage → 访问列表页）
3. 运行 dongchedi_l90_watch.py 使用该 profile
4. 可保留 profile 供下次使用（会累计 cookies）

当前 WSL 环境 `--headed` 需要 `xvfb-run` 包装。headless 模式下预热同样有效 — 只要 browser context 建立过会话 cookie 即可。
