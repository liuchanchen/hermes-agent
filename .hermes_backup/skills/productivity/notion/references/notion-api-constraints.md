# Notion API Constraints Discovered in Practice

## PATCH /pages/{id}/markdown — Body Format Rejected

The Notion API docs show `PATCH /v1/pages/{page_id}/markdown` with a `markdown` body param,
but in practice it returns:

```
HTTP 400: body failed validation: body.type should be defined, instead was `undefined`
```

The endpoint only accepts the block append format (`PATCH /v1/blocks/{page_id}/children`)
with explicit block objects. The `markdown` shorthand only works on **create** (`POST`), not
on patch/update.

**Working approach:** Always use block append for both creating and updating content:
```python
body = json.dumps({"children": [...blocks...]})  # blocks = list of block dicts
PATCH https://api.notion.com/v1/blocks/{page_id}/children
```

## Code Block Max Length: 2000 Characters

Notion code blocks truncate `rich_text[0].text.content` at 2000 chars. Longer scripts
must be split across multiple blocks or linked externally.

Workaround: reference the script path and note that full content is at `/tmp/script.py`.
For production use, upload as a file attachment (see below) or split into ≤2000 char chunks.

## Callout Emoji: Valid Emoji Set Only

`callout.icon.emoji` only accepts actual Unicode emoji, not arbitrary text strings.
Invalid values like `"WARNING"`, `"INFO"`, `"ALERT"` are rejected with:

```
body.children[N].callout.icon.emoji should be `"😀"`, `"😃"`, ...
```

Use real emoji: `"⚠️"` for warnings, `"💡"` for tips, `"📁"` for files, `"✅"` for success.

## Table Blocks: `table_width` Required

Every `table` block object needs `"table_width"` field (integer, number of columns).
Omitting it causes:

```
body.children[N].table.table_width should be defined
```

Correct minimal table block:
```python
{
    "object": "block", "type": "table", "table": {
        "table_width": 2,  # required: number of columns
        "has_column_header": True,
        "has_row_header": False,
        "cells": [[...cells for column 1...], [...cells for column 2...]]
    }
}
```

## File Blocks: External URL Only

`file` block type with `"type": "external"` only accepts HTTP(S) URLs. `file:///` local paths
are rejected as invalid:

```
Content creation Failed. Invalid file url.
```

**Workaround:** Embed a callout with the local file path instead of an actual image/file embed.
File uploads to Notion (via `POST /v1/file_uploads`) exist but only work for attaching to
Notion database properties, not as inline page blocks via the REST API alone.

For script files, use a code block instead of file upload. For images, either:
1. Upload to a public URL (Imgur, S3, etc.) and use `"external": {"url": "https://..."}`
2. Store locally and reference the path in a callout block

## File Upload API (POST /v1/file_uploads)

```python
# Step 1: Create upload
POST https://api.notion.com/v1/file_uploads
{"filename": "photo.png", "content_type": "image/png"}
# Returns: {"id": "...", "upload_url": "https://api.notion.com/v1/file_uploads/{id}/send", "expires_at": "..."}

# Step 2: PUT the file bytes to upload_url
PUT {upload_url}
Content-Type: image/png
[binary file content]

# Step 3: Use the upload ID in a page property (not as a block)
```

Supported `content_type` values: `image/png`, `image/jpeg`, `image/gif`, `image/webp`,
`application/pdf`, and some others. `.py` files are **NOT supported** — rejected with:

```
Provided `filename` has an extension that is not supported for the File Upload API.
```

## Rate Limiting Notes

- ~3 req/s average; no burst penalty observed
- No retry-after header in 429 responses; use exponential backoff

## Verified Working Block Types (2026-06-03)

| Block Type | Status | Notes |
|-----------|--------|-------|
| `heading_2` / `heading_3` | ✅ | `rich_text` with `text.content` |
| `paragraph` | ✅ | |
| `callout` | ✅ | `icon.emoji` must be real emoji; `color` = `*_background` |
| `code` | ✅ | `language` = python/bash/etc.; max 2000 chars per block |
| `bulleted_list_item` | ✅ | |
| `numbered_list_item` | ✅ | |
| `table` | ⚠️ | Requires `table_width` |
| `file` (external) | ⚠️ | Only HTTPS URLs |
| `divider` | ✅ | No content needed |