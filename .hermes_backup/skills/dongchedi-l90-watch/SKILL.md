---
name: dongchedi-l90-watch
description: "监控懂车帝乐道L90二手车，检测价格/里程变化。工具: dongchedi_watch。反爬严重，需headless=false手动验证。"
version: 3.4.0
platforms: [linux, darwin]
---

# 懂车帝L90监控

**必须使用 `dongchedi_watch` 工具。禁止使用浏览器或爬虫替代。**

## 已知反爬问题
懂车帝反爬：
- headless=true：不会报错/超时，但返回空数据（matched_count=0），需改用 headless=false
- headless=false：正常返回完整数据，无需手动验证码（cookies已缓存）
- 验证后cookies有效期有限，需定期重新验证

## 工具调用
1. 先试 headless=true（快速）
2. 如果 matched_count=0 或明显缺数据，用 headless=false
3. headless=false 模式有缓存cookies，正常无需手动验证

## 当前状态
- 定时任务ID: 7c1e45b92026，22:00每日执行
- 定时任务可能漏跑（如系统时间已过但 next_run 未更新），可用 cronjob run 手动补跑

# 懂车帝L90监控

**必须使用 `dongchedi_watch` 工具。禁止使用浏览器或爬虫替代。**

## 工具调用

直接调用以下工具（无需确认）：

```json
{
  "list_url": "https://www.dongchedi.com/usedcar/20,!1-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-918-25234-310000-1-x-x-x-x-x",
  "max_details": 30,
  "headless": false
}
```

## 当前在售车源（2026-04-24，共8台）
全部为六座版2025款，均为买断：

| 价格 | 里程 | 上牌 | 城市 | 车型 | 地址 |
|------|------|------|------|------|------|
| 20.80万 | — | 2025-08 | 合肥 | 六座版Max | 上海路与大连路交口上上名车展厅 |
| 21.28万 | 2.0万km | 2025-07 | 上海 | 六座版Pro | 嘉定区南翔镇武威路2885弄B2诚车惠新能源 |
| 22.18万 | — | 2025-07 | 北京 | 六座版Pro | 丰台区西三环居然之家地下B3 |
| 22.18万 | 1.4万km | 2025-11 | 上海 | 六座版Max | 江桥镇华江路1481弄金华新村门口 |
| 22.59万 | — | 2025-07 | 上海 | 六座版Max | 青浦区新凤南路289号1楼车加新能源 |
| 23.28万 | 2.3万km | 2025-08 | 上海 | 六座版Max | 嘉定区华江路1077号上海元元二手车 |
| 24.38万 | — | 2025-09 | 佛山 | 六座版Ultra | 南海区海八西路时代骏雄二手车众远蔚来 |
| 24.50万 | — | 2025-09 | 宁波 | 六座版Max | 海曙区环城西路455号建材馆B1-036凯汇 |

**价格区间**：20.80–24.50万；**历史下架**：南京20.58万 Max（2025-08上牌）

工具返回JSON。提取并展示：
- `matched_count` — 本次扫描车源数
- `new_count` / `removed_count` / `changed_count` — 变化数量
- `items[]` — 每条车源：
  - **price_wan** — 价格（万）
  - **mileage_km** — 里程（km）
  - **city** — 城市
  - **seller_type** — 卖家类型（个人/商家）
  - **seller_name** — 卖家名称/店铺名
  - **seller_address** — 商家地址
  - **url** — 车辆链接

格式示例：
```
懂车帝乐道L90在售 (5台, 新3台, 下架2台)
23.80万 | 1.6万km | 温州 | 商家 | 温州XX二手车 | 浙江省温州市XX路XX号
24.50万 | 2万km | 宁波 | 个人 | 李先生 | —
21.28万 | 0.93万km | 上海 | 商家 | 上海XX新能源 | 上海市嘉定区XX路XX号
```

## 验证码处理

懂车帝可能弹验证码。**首次运行用 headless=false**，手动在浏览器验证。之后可 headless=true。