# Worked examples — 吉安/Ji'an prefecture research (2026-08-04)

Session examples used to validate the skill. Keep as condensed reference, not a full mirror of sources.

## Example 1: 敦厚镇 Dunhou Town (吉安县 county seat)

Reliable path used: 百度百科 (baike.baidu.com/item/敦厚镇) reached instead of blocked search engines. Extracted via browser_console JS from `.main-content`.

Key facts captured:
- 隶属: 江西省吉安市吉安县; located 禾水河下游, is 吉安县治 (county seat)
- 面积 89 km²; 下辖 8社区+19村 (2020); 户籍人口 ~13.25万 (2019末)
- 名称由来: "敦厚" = 谐音 "圳头", 取诚恳/淳厚
- 沿革: 1958敦厚公社 → 1971始建县城 → 1979.10设敦厚镇为县治 → 2001.12高塘乡并入
- 地理: 亚热带湿润季风, 年均温18.4℃, 年降水~1400mm; 禾河过境汇赣江
- 经济: 2018财政收入1821.51万元 (+14.5%); 187家工业企业 (87规模以上, 2019末)
- 交通: 105国道纵贯南北, 吉井公路横穿, 赣粤高速出入口, 吉井铁路; 距吉安站12km, 井冈山机场30km
- 景点: 文天祥纪念馆 (正气堂), 天祥公园 (2011), 白鹭洲书院
- 名人: 余秋里 (1914-1999), 敦厚镇坪里村人, 开国中将, 石油工业部/计委/国务院副总理/总政治部主任

## Example 2: 井冈山市 (county-level city under 吉安)

Reliable path: 维基百科 zh.wikipedia.org/wiki/井冈山市 — infobox carried the definitive administrative-relation answer.

Answer to "is 井冈山 part of 吉安": YES — 井冈山市 is a 县级市 directly under 吉安市 (地级市), NOT part of 吉安县.

Key infobox facts:
- 隶属行政区: 江西省吉安市
- 区划代码 360881; 车牌 赣D (shared by all 吉安 counties → confirms prefecture grouping)
- 面积 ~1,276 km²; 常住人口 155,976 (2020)

## JS extraction snippet that worked on 百度百科

```js
(() => {
  const main = document.querySelector('.main-content') || document.querySelector('.J-lemma-content') || document.body;
  return main.innerText.substring(0, 8000);
})()
```
