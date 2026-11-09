---
name: notion-api-block-writing
description: Fill existing Notion pages via the block API.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [notion, api, blocks, tables, markdown, publishing]
    related_skills: [notion]
---

# Notion API Block Writing

How to write structured content (tables, headings, bullets, paragraphs) into an
EXISTING Notion page under specific headings, using the block REST API. This is
the practical, verified companion to the bundled `notion` skill — it documents
the exact API pitfalls that are easy to trip over when the page already has a
header structure you must fill underneath.

## When to Use

- User asks to fill experiment/report/plan results into an EXISTING Notion page
  "following the desired header" — the page already has
  `## 实验目标 / ## 实验设计 / ## 实验结果`-style headings and you must insert
  content under each without disturbing them.
- You need to write Notion tables via the block API and hit the table-cell
  validation error.
- You need to insert blocks at a specific position (not just append at the end).

## Prerequisites

- `NOTION_API_KEY` in `~/.hermes/.env` (integration token), page shared with the
  integration (else 404).
- Base URL `https://api.notion.com/v1`, header `Notion-Version: 2025-09-03`,
  `Authorization: Bearer $NOTION_API_KEY`.
- **The PATCH markdown shorthand does NOT work on existing pages**
  (`PATCH /v1/pages/{id}/markdown` → `HTTP 400: body.type should be defined`).
  It only works on CREATE. For filling an existing page you MUST use
  `PATCH /v1/blocks/{page_id}/children` with explicit block objects.

## Core recipe

1. **Read current structure** — `GET /v1/blocks/{page_id}/children`, walk
   recursively (`has_children`) to see which headings exist and whether content
   is already under them. The page may start with ONLY the headings (no content).

2. **Find heading block IDs** — match `heading_2` blocks by their
   `rich_text[].plain_text` concatenation to get the block id to insert after.

3. **Build block JSON** (see Table cells below — the #1 bug).

4. **Insert each section after its own heading** using the `after` parameter.

5. **Verify** — re-fetch children, count blocks per type (tables/rows/bullets),
   and spot-check table cell text. Then optionally fetch
   `GET /v1/pages/{id}/markdown` to eyeball the final document.

## Table blocks: the `cells` nesting bug (verified 2026-08-20)

`table_row.cells` is a **list of cell-arrays**, and each cell is itself a
**list of rich_text objects**. The flat form is WRONG and Notion rejects it with
a MISLEADING error:

```
Content creation Failed. Fix the following:
Number of cells in table row must match the table width of the parent table
```

WRONG — each row becomes ONE cell containing N texts (width mismatch):
```python
cells = [{"type": "text", "text": {"content": c}} for c in row]
{"type": "table_row", "table_row": {"cells": [cells]}}
```

CORRECT — one list per cell:
```python
cells = [[{"type": "text", "text": {"content": c}}] for c in row]
{"type": "table_row", "table_row": {"cells": cells}}
```

Block shape:
```python
{"object": "block", "type": "table", "table": {
    "table_width": ncols,
    "has_column_header": True,
    "has_row_header": False,
    "children": [ ...table_row blocks... ],
}}
```

If the error says "cells must match table width" and your row counts look right,
suspect this nesting FIRST — the error message is about width but the real bug
is almost always the cell structure.

## Append API and table `children` (verified 2026-09-05)

Two related traps when appending to a page:

1. **Table `children` IS accepted on the page-children append** — a `table` block
   appended via `PATCH /blocks/{page_id}/children` REQUIRES `table.children` to be
   present (list of `table_row` blocks). A table with only `table_width` + inline
   `cells` fails with `body.children[N].table.children should be defined, instead was
   undefined`. (The no-nested-`children` rule below applies to nested LIST blocks,
   not to table rows.)
2. **Read-back quirk**: after appending, the top-level page-children listing shows the
   table with 0 rows. Verify rows via a second fetch: `GET /blocks/{table_block_id}/children`
   → expect header + data rows, spot-check cell text.

## Append API rejects "children" on block objects (verified 2026-09-04)

`PATCH /blocks/{page_id}/children` does NOT accept nested blocks: any block
object carrying a `children` field fails with `validation_error: body.children[N].<type>
should be defined, instead was undefined` (the error lists every block type —
misleading, the real cause is the `children` field itself). Nested bullet
lists therefore CANNOT be created in the same append payload as their parent.

Workaround: flatten sub-bullets to top-level `bulleted_list_item` blocks with
a visual prefix (e.g. `· `) on the text. Verified working for a 105-block
notes page.

Also: append requests are slow (~1.5-2s per chunk incl. rate-limit sleep); a
105-block rewrite exceeds a 240s foreground timeout — always run as a
background process with notify, like clears.

## Markdown tables: separator rows (verified 2026-08-26)

When converting a markdown table to a Notion `table` block, the `|---|---|`
separator row between header and body must be **skipped IN-PLACE, NOT treated as
a table-end trigger**. If your converter flushes/emits the table on the separator
line, the header row and body rows land in **two separate table blocks** (and the
separator becomes a stray block between them), and the page shows "header and
body separated" instead of one table.

The separator check is a per-line `continue`, never a flush:

```python
if line.startswith("|"):
    cells = [c.strip() for c in line.strip("|").split("|")]
    if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
        i += 1; continue          # separator: skip, KEEP the table open
    table_buf.append(cells)
    i += 1; continue
# ...only a NON-| line flushes the table...
```

Signs you hit this bug: the page has ~2× the markdown's table count, or each
markdown table renders as a header-only table followed by a body-only table.
Verify by counting `table` blocks vs. source tables — they must match exactly.
The shipped `scripts/notion_clear_rewrite.py` implements this correctly; copy its
`make_blocks` when writing your own converter.

## Editing an existing block in place (verified 2026-08-20)

To modify text inside an existing block (e.g. relabel a table header cell),
PATCH the block directly — no need to rebuild or re-append the whole table:

```python
# 1. Fetch the row block to get its current cells
row = api("GET", f"/v1/blocks/{row_id}")          # {"table_row": {"cells": [...]}}

# 2. Mutate ONLY the target column; keep every other cell unchanged
cells = row["table_row"]["cells"]
cells[col_idx] = [{"type": "text", "text": {"content": "new text"}}]

# 3. PATCH the full row back with all cells
api("PATCH", f"/v1/blocks/{row_id}", {"table_row": {"cells": cells}})
```

Key points:
- The block PATCH replaces the ENTIRE `table_row.cells` array — you must send back
  all columns (copy the fetched cells, mutate one), not just the cell you changed.
- Same pattern works for any block type: fetch the block, mutate its `rich_text` /
  `cells`, PATCH the whole block payload back.
- Verify with `GET /v1/pages/{id}/markdown` — the markdown will show the new
  `<td>...</td>` text so you can confirm without re-fetching every block.
- This is the right approach when a column header or annotation needs a parenthetical
  explanation added AFTER content was already written (e.g. appending
  `（Mooncake 恢复延迟 ÷ 基线重算延迟，<1 表示 Mooncake 更快）` to a `TTFT ratio` header).

## Inserting content under a heading — reverse order (verified 2026-08-20)

`PATCH /v1/blocks/{page_id}/children` accepts `"after": "<block_id>"` to insert
blocks immediately after an existing block. To fill under headings A, B, C
(which appear in that order) WITHOUT interleaving, process from the LAST
section backward:

```
page children = [A, B, C]
1) insert C-content after C → [A, B, C, C-content]
2) insert B-content after B → [A, B, B-content, C, C-content]
3) insert A-content after A → [A, A-content, B, B-content, C, C-content]  ✓
```

If you process forward (A first), B's content lands BETWEEN A-content and B
because "after A" = "right before B".

For multi-chunk sections, pass `after` only on the FIRST chunk; subsequent
chunks append after the section (their order is preserved as long as each chunk
only contains that section's blocks). Chunk to ≤60 blocks per request to stay
safely under the 100-block append limit and the ~3 req/s rate limit.

## Idempotency for partial failures (verified 2026-08-20)

When one section's append fails (e.g. a table validation error), the OTHER
sections' PATCHes may still have SUCCEEDED. The failed section is the only one
missing.

1. Re-fetch children FIRST — count which headings already have content.
2. Make the fill script accept a `FILL_SECTIONS` env/arg filter (comma list of
   section titles) so you only re-run the failed section.
3. Re-running everything after a partial failure DUPLICATES the succeeded
   sections — always filter before retry.

## Block types that work reliably

- `heading_3` / `paragraph` / `bulleted_list_item` / `numbered_list_item` /
  `table` / `divider` — all fine via the block append API.
- Table validation error above is the one that bites; everything else is
  straightforward rich_text `{"type":"text","text":{"content": s}}`.

## Clearing / rewriting a page wholesale (verified 2026-08-26)

To replace a page's content (e.g. re-import a stale knowledge base) DON'T
recreate the page — **clear its blocks, then append fresh ones**.

1. **Clear = recursive DELETE.** List top-level children (paginate 100/req),
   then DELETE each block **after** its descendants (children first, parent
   last — DELETE on a block with children fails). `DELETE /v1/blocks/{id}`
   archives the block; works for tables, nested bullet lists, everything.
   Verify by re-fetching children → 0 results.

2. **Run clear/write as a BACKGROUND script, not execute_code.** A 200+
   block page exceeds execute_code's 300s wall-clock cap, and on timeout it
   kills the run with buffered stdout lost. Write the script to a file and
   launch `terminal(background=true, notify_on_complete=true)`, printing
   progress with `flush=True` every N items.

3. **Rate limit ~3 req/s, no Retry-After header.** Sleep ~1.5s between
   requests and wrap every call in a retry-on-429 loop. A 320-block page
   takes minutes — let it run, don't kill it.

4. **Repopulate = markdown → block JSON, append in chunks ≤60.** Notion's
   `markdown=` shorthand only works on page CREATE; you cannot PATCH markdown
   onto an existing page (HTTP 400). Convert the file yourself: headings_1-3,
   paragraphs, bulleted_list_item, quote, divider, code (cap ~1800 chars/block),
   table (cells nesting per the Table section above). Strip `**bold**` and
   `` `code` `` markers from paragraph text — Notion rich_text doesn't
   auto-render them. Append with `PATCH /blocks/{page_id}/children` in ≤60-block
   chunks, verifying each chunk's `_error` before continuing.

5. **Verify by re-reading children** (both pages if >100) and spot-check the
   first and last blocks (title, closing references).

Ready-to-run: `scripts/notion_clear_rewrite.py` — `clear|write|rewrite <page_id> [<md_file>]`, reads `NOTION_API_KEY` from `~/.hermes/.env`.

## Pitfalls

- **Page content created with `markdown=` on POST is fine**, but you cannot
  PATCH markdown onto an existing page — always block-append.
- **Rate limit ~3 req/s** — no retry-after header on 429; back off and retry.
- **`Notion-Version: 2025-09-03` is mandatory** on every request.
- **Code blocks truncate at 2000 chars** — split long scripts across blocks.
- **`after` is supported on `PATCH /v1/blocks/{page_id}/children`** — that's the
  endpoint to use for insertion.
- **Read-only verification is cheap**: GET children + GET page markdown to
  confirm before declaring done.
- **Simplest reliable table append (2026-09-05)**: build `table` block with
  `table_width` + `has_column_header` + `children` = [`table_row` blocks], each row's
  `cells` = list of per-cell rich_text ARRAYS (see Table section). Single PATCH of the
  whole payload works up to ~21 blocks incl. a 13-row table; verify via the table
  block's own children endpoint.
