---
name: china-admin-geography-research
description: Research China's administrative-geographic places (provinces, cities, counties, towns) and administrative-division relationships (地级市/县级市/县治) using browser tools. Use when the user asks to introduce a Chinese city/town, whether place X belongs to place Y, administrative divisions, or county-seat facts.
---

# China Administrative-Geography Research (中国行政区划查询)

Research class: introducing a Chinese administrative place, or clarifying administrative-division relations (e.g. "is 井冈山 part of 吉安?"). Covers 省→地级市→县级市/县→镇 hierarchy, 县治 (county seat), and cross-checking place facts.

## Default assumptions for questions like "is X part of Y"

The user often conflates two levels of the same-named place. Disambiguate explicitly:
- **地级市 vs 县** are NOT the same unit. E.g. 吉安(地级市, prefecture-level city) ⊃ {吉安县(县) + 井冈山市(县级市) + ...}. 井冈山 belongs to 吉安(地级市) but is NOT part of 吉安县.
- **县级市** (county-level city, e.g. 井冈山市): directly administered by the prefecture-level city, not by a county. Confirm via Wikipedia infobox "隶属行政区".
- **镇 is the 县治 (county seat)** often — e.g. 敦厚镇 is 吉安县's seat. Note when a town is the seat, it carries the county's administrative/economic center role.
- Quick structural confirmations: 行政区划代码 (区划代码) — the 2nd two digits encode the prefecture; 车牌号 (plate codes) are shared across a prefecture (e.g. all 吉安 counties = 赣D).

## Reliable source workflow (do NOT start with a search engine)

Automated browsers hit anti-bot on the general search engines — do not burn turns there:
- **baidu.com/s** → `wappass.baidu.com` CAPTCHA
- **sogou.com/web** → `antispider` block
- **duckduckgo.com/html** → anti-bot checkbox
- **bing.com/search** → Cloudflare "Verify you are human" challenge

**Go directly to the two encyclopedias instead:**

1. **百度百科** — `https://baike.baidu.com/item/<词条名>` (URL-encoded). Richest structured data: 建置沿革, 行政区划(list of villages/communities), 地理环境, 经济, 交通, 历史文化, 著名人物. Usually has the most complete modern data.
2. **维基百科** — `https://zh.wikipedia.org/wiki/<词条名>`. Best infobox for administrative relationships (隶属行政区), 区划代码, 车牌, 面积, 人口. Note zh.wikipedia needs the language-variant table — infobox cells carry the key facts.

Wikipedia terms to trust from the infobox: `国家`, `隶属行政区` (=上级行政区 = answers "belongs to X"), `行政区划代码`, `车辆號牌`, `面积`, `人口`, `村级区划单位数`.

## Extract article body via JS — do not scroll the accessibility tree

`browser_snapshot(full=true)` on these encyclopedias returns an enormous, truncated accessibility tree. **Extract text directly with browser_console + JS**:

```js
(() => {
  const main = document.querySelector('.main-content') || document.querySelector('.J-lemma-content') || document.body;
  return main.innerText.substring(0, 8000 DISPLAY-CHAR-CAP);
})();
```

- 百度百科 content lives in `.main-content` / `.J-lemma-content` / `.lemma-summary`.
- Fall back to `document.body.innerText` if those miss; `substring(0, ~8000)` keeps the reply manageable and pulls the intro + first sections.
- This returns clean text with section headers intact (建置沿革, 行政区划, ...) — far more reliable than parsing the a11y tree.

## Data hygiene / cross-checking

- Multiple years of population/enterprise data appear (2017/2018/2019/2020 figures). Cite the year; note "可能已变化" if data is years old, and offer to pull the latest county/yearbook if the user wants current numbers.
- Cross-check borderline claims against both 百科 + Wikipedia when possible. If a claim (e.g. exact historical 沿革 year) is not 100% certain, say so and offer to verify, per the user's "不要写不确定的数据" correction preference.
- 著名人物 (notable locals) — verify the 籍贯 detail (village) it lists before asserting.

## References

- `references/jian-examples.md` — worked examples (吉安 prefecture: 敦厚镇, 井冈山市) with captured facts and the confirmed JS extraction snippet.

## Pitfalls

- The question "does X belong to Y" is a trap for level-confusion — always state *which level* of Y (地级市 vs 县) X belongs to.
- 县级市 ≠ 市辖区. Names like 井冈山市 are county-level cities, not 区 (district) of the prefecture city.
