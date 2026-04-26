---
name: dongchedi-l90-watch
description: "监控懂车帝乐道L90二手车，检测价格/里程变化。脚本: dongchedi_l90_watch.py + xvfb-run"
version: 4.1.0
platforms: [linux]
---

# 懂车帝L90监控

**正确方法：用 `xvfb-run` 运行 Python 脚本（不要用 browser 工具）**

## 依赖安装（首次）
```bash
cd /home/jianliu/work/hermes-agent && source venv/bin/activate
uv pip install crawl4ai
playwright install chromium
```

## 运行命令
```bash
xvfb-run -a python tools/dongchedi_l90_watch.py \
  --list-url "https://www.dongchedi.com/usedcar/20,!1-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-918-25234-310000-1-x-x-x-x-x" \
  --db /home/jianliu/.hermes/dongchedi_l90.db \
  --max-details 30 \
  --profile-dir /tmp/dongchedi_profile
```

## 关键要点

### xvfb-run 是必须的
- 脚本内部即使 `headless=True` 也会启动非 headless Chrome（crawl4ai 的 BrowserConfig 默认 headed）
- WSL 无 X server，不加 xvfb-run 会报错 "TargetClosedError: BrowserType.launch_persistent_context: Target page, context or browser has been closed" + "looks like you launched a headed browser without having a XServer running"
- `xvfb-run -a` 自动分配虚拟显示（`:99` 等）

### 数据库注意事项
- 旧 DB (`~/.hermes/dongchedi_l90.db`) 的 schema 可能不兼容（缺 `platform` 列）
- 用新 DB 或空字符串 `--db ""` 创建新库
- 推荐 DB 路径：`/home/jianliu/.hermes/dongchedi_l90.db`

## 定时任务配置
- Job ID: 7c1e45b92026
- Schedule: 每天 22:00 (`0 22 * * *`)
- **注意**：cron job 默认 toolset 只有 `hermes-cli`，无法直接调用工具。需用 Python 脚本方式或确保 job 有 `browser` toolset
- deliver 必须设为 `"origin"` 才能发送结果

## 已知问题

1. **browser 工具无法访问懂车帝** — `browser_navigate` 返回 `ERR_ABORTED`，即使 baidu.com 正常。**不要用 browser 工具**
2. **dongchedi_watch 不是工具** — 是 Python 脚本，不是 MCP 工具或 pip 包
3. **旧数据库 schema 不兼容** — `no such column: platform` → 用新 DB

## 当前在售（2026-04-24，共9台）

| 价格 | 里程 | 上牌 | 城市 | 车型 | 地址 |
|------|------|------|------|------|------|
| 21.80万 | — | 2025-08 | 太原 | 六座版Max | 晋源区万国精品二手车市场 |
| 20.80万 | — | 2025-08 | 合肥 | 六座版Max | 上海路与大连路交口上上名车展厅 |
| 21.28万 | 2.0万km | 2025-07 | 上海 | 六座版Pro | 嘉定区南翔镇武威路2885弄B2诚车惠新能源 |
| 22.18万 | — | 2025-07 | 北京 | 六座版Pro | 丰台区西三环居然之家地下B3 |
| 22.18万 | 1.4万km | 2025-11 | 上海 | 六座版Max | 江桥镇华江路1481弄金华新村门口 |
| 22.59万 | — | 2025-07 | 上海 | 六座版Max | 青浦区新凤南路289号1楼车加新能源 |
| 23.28万 | 2.3万km | 2025-08 | 上海 | 六座版Max | 嘉定区华江路1077号上海元元二手车 |
| 24.38万 | — | 2025-09 | 佛山 | 六座版Ultra | 南海区海八西路时代骏雄二手车众远蔚来 |
| 24.50万 | — | 2025-09 | 宁波 | 六座版Max | 海曙区环城西路455号建材馆B1-036凯汇 |

**价格区间**：20.80–24.50万 | 全部电池买断 | 全部商家