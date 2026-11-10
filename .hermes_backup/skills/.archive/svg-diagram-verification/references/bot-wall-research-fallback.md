# Research discovery fallback: search engines are bot-walled

Encountered 2026-08-10 while researching "EcoServe LLM serving" + "TGU01-F"
against a headless browser. **Every general search engine blocked the browser
with a CAPTCHA/bot wall** — this is the norm, not the exception, in headless
environments:

| Engine | Result |
|--------|--------|
| Bing | returned irrelevant results, then "solve challenge" wall |
| Google | `/sorry/index` CAPTCHA |
| Baidu | `wappass.baidu.com` CAPTCHA (tuxing_v2) |
| Sogou | `antispider` wall |
| Toutiao (so.toutiao.com) | slider-captcha iframe |
| DuckDuckGo HTML | "Select all squares containing a duck" |

## What DOES work: the source's OWN search

For academic/technical lookups, **skip the engines and go straight to the
primary source's site search** — it is rarely bot-walled the same way:

```
# arXiv (this saved the session)
https://arxiv.org/search/?query=EcoServe+LLM&searchtype=all
```

- `searchtype=all` searches title + abstract + full text.
- Returns the arXiv ID, title, authors, and abstract inline — enough to
  confirm "is this the right paper?" and grab the ID without scraping.
- General lesson: when searching for a paper/product/spec, try the
  publisher's/vendor's own search UI before fighting general engines.

## Reading a specific paper section (algorithms, formulas)

`web_extract` on the abstract page gives metadata + abstract. To pull a
*specific section* (an algorithm, pseudocode, a design subsection), the
experimental HTML page is greppable via `browser_console`:

```
browser_navigate(url="https://arxiv.org/html/{id}")
browser_console(expression="(()=>{const t=document.body.innerText;const i=t.indexOf('3. Design');return t.slice(i,i+6000);})()")
```

`document.body.innerText` is plain readable text (math renders as readable
symbols). Slice by section-heading `indexOf`, or scrape the positions of all
subsection markers first (loop `indexOf` over `['3.1','3.2',...]`) to find the
exact range, then pull just that slice — avoids dragging a whole 1756-line
paper into context.

Beware: navigating a search engine mid-session can leave the browser stuck on
a "solve the challenge" interstitial — re-navigate to the clean source URL (the
arXiv page) to recover; don't keep fighting the wall.
