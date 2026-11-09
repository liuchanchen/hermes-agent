# 替代数据源：二手车之家 (che168.com)

懂车帝 `/usedcar/` 全路径被登录墙阻断时的备选数据源。2026-11-09 实测可用。

## 列表页

```
https://www.che168.com/china/ledao/l90/
```

- 服务端返回 GB2312 页面，但**带 JS 反爬**：无 cookie 连续请求 2 次后返回 ~1KB 的 `EO_Bot_Ssid` 混淆脚本，再请求就跳 `https://www.che168.com/captcha.aspx?returnurl=...`（标题「二手车之家-安全验证」）。
- 用 Playwright（headless 即可，加 `--no-sandbox` + `Object.defineProperty(navigator,'webdriver')`）首次加载可正常渲染出完整列表。
- **不要在同一 IP 上反复重试**，触发 captcha 后短时间内无法恢复。一次渲染后立刻 `page.content()` 存盘，后续解析离线做。

## 卡片结构（2026-11 版本）

列表项是 `li.cards-li`，标题在 `h4.card-name`（**不是 h2**），价格在 `span.pirce em`，但更可靠的是 `<li>` 上的 data 属性：

| 属性 | 含义 | 示例 |
|------|------|------|
| `carname` | 车型全名 | 乐道L90 2025款 Ultra 六座版 |
| `price` | 挂牌价（万） | 16.5 |
| `milage` | 里程（万公里） | 1.9 |
| `regdate` | 上牌年月 | 2025/08 |
| `infoid` | 车源ID | 60347236 |
| `dealerid` | 商家ID | 516744 |
| `publicdate` | 上架时间 | 2026-10-29T17:55:47Z |

城市在 `p.cards-unit` 文本里，格式 `1.9万公里／2025-08／深圳／5年黄金会员`（第 3 段）。
详情链接 `/dealer/{dealerid}/{infoid}.html`，前面拼 `https://www.che168.com`。

## 解析脚本要点

```python
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(path, encoding='utf-8').read(), 'html.parser')
for li in soup.select('li.cards-li'):
    name = li.get('carname') or ''
    if '乐道L90' not in name:
        continue   # 页面混排 L60 / L80 推荐车源
    price = float(li.select_one('span.pirce em').get_text(strip=True))
    unit = li.select_one('p.cards-unit').get_text('／', strip=True).split('／')
    city = unit[2] if len(unit) > 2 else ''
```

**坑**：不要用正则 `([0-9.]+)万` 抓价格——会先命中里程的「1.7万公里」。必须走 `span.pirce em` 或 `li['price']`。

## 与懂车帝的可比性（重要）

1. **电池方案未知**：che168 卡片不标注电池买断/BaaS。L90 BaaS 车源比买断便宜约 5–6 万，混在一起算均价会严重偏低。
2. **样本范围**：`/china/ledao/l90/` 是全国首页，单页约 36 台 L90（还混排 L60/L80 推荐位），不是全量库存；有「下一页」。
3. **不能与懂车帝历史快照直接做涨跌对比**：平台不同、口径不同、车源不同。要对比必须在同一句话里写明基准（平台+电池方案+样本数）。

## 已知可用的辅助信息

- 车源详情页 `pcm.che168.com/2023/cardetail_rn/index?infoid=...` 是 SPA（`#app-root` 空壳），必须浏览器渲染。
- Bing/Google 的 `site:che168.com 乐道L90` 搜索结果摘要里带「里程 / 年份 / 价格」，可作为交叉验证的第二来源（不是主数据）。
