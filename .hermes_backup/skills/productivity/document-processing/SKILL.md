---
name: document-processing
description: PDF and document processing — OCR text extraction (pymupdf, marker-pdf), PDF text editing via NLP prompts (nano-pdf), and Office document conversion
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, OCR, Document-Processing, Text-Extraction, nano-pdf]
---

# Document Processing

Extract text from, edit, and convert documents. Covers PDF text extraction via multiple backends, PDF text editing with NLP prompts, and Office file conversion.

## Quick reference

| Task | Tool | When to use |
|------|------|-------------|
| URL → text | `web_extract(url)` | First try for any document URL |
| Light PDF text | pymupdf | Simple text-based PDFs (~25MB, instant) |
| Complex PDF OCR | marker-pdf | Scanned docs, equations, forms (~3-5GB) |
| Edit PDF text | `nano-pdf edit` | Fix typos, update content via NL prompt |
| DOCX → text | python-docx | Word document extraction |
| ASCII-diagram in docx→PNG | `references/diagram-rendering-via-headless-chrome.md` | redraw as HTML/CSS + headless Chrome screenshot + crop + embed |
| Render Office→image for QA | `references/office-render-via-windows-powershell.md` | soffice NOT installed (WSL) — render via Windows PowerPoint COM + pixel/geometry QA |

## 1. PDF Text Extraction

### Strategy (try in order)
1. **URL-first**: `web_extract(urls=[doc_url])` — works for most Arxiv, web-hosted PDFs
2. **pymupdf** (instant, lightweight): For text-based PDFs on local filesystem
3. **marker-pdf** (OCR, heavy): For scanned documents, equations, complex layouts

### pymupdf (recommended first for local files)
```python
import fitz  # pip install PyMuPDF
doc = fitz.open("file.pdf")
text = "\n".join(page.get_text() for page in doc)
```

### marker-pdf (for OCR / complex layouts)
```bash
pip install marker-pdf
marker_single file.pdf output_dir/
```

## 2. PDF Text Editing (nano-pdf)

```bash
nano-pdf edit document.pdf 3 "Fix the typo in the third paragraph"
nano-pdf edit document.pdf 1 "Change the title to 'Annual Report 2026'"
```

Page numbering may be 0-based or 1-based depending on version. Best for simple text edits. Complex layout changes should use other methods.

## 3. Markdown → Word (.docx) CREATION

When asked to "output a markdown doc to Word", build a `.docx` with python-docx (pure-Python, needs `pip install python-docx`). Write a small markdown→docx converter yourself for full control (headings, pipe tables, ``` code blocks, `>` blockquotes, `-`/`1.` lists, `**bold**` inline). A full working converter template lives in `templates/md2docx_converter.py`.

### Environment pitfalls on this WSL box (both bite — use the workarounds)
1. **The shell `python3`/`python` hangs on a broken conda-activation wrapper** — prints "An unexpected error has occurred. Conda has prepared the above report." and blocks forever. Workaround: call the conda binary directly: `/home/jianliu/miniconda3/bin/python <script>`. Verify first with `/home/jianliu/miniconda3/bin/python -c "import docx"`.
2. **python-docx NAMED-STYLE lookups hang against the default template.** `doc.add_heading("x", level=n)` and `doc.add_paragraph(style="List Bullet"/"List Number")` deadlock deep in `docx.oxml.xmlchemy.xpath` → `styles.get_by_name` (the default template has no resolvable 'Heading N' / 'List *' styles, so the lookup loops). Workaround: DON'T use named styles. Render headings as ordinary bold paragraphs (per-level `Pt` size), lists as plain paragraphs with a manual "• "/"1. " prefix, set fonts via direct run formatting.

### Diagrams / ASCII art in Word: render to PNG and embed (do NOT keep as code)
Box-drawing ASCII diagrams (`┌─┐ │ ▼`) DO NOT render well in Word: box chars and CJK are full-width, ASCII is half-width, so columns misalign no matter the font, and Word's line-spacing/shrink-to-fit makes it worse. Fix: rebuild the diagram as styled HTML/CSS boxes and screenshot to PNG with headless Chrome, then embed the image. Full recipe + gotchas in `references/diagram-rendering-via-headless-chrome.md`. Embedding a picture in python-docx:
```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture("diagram.png", width=Inches(6.3))  # fit letter margins
```
Converter variation that auto-embeds diagram blocks: sniff each ` ``` ` block for box-drawing chars (`─┌┐└┘│┬┴▼`); if present and a matching image exists, embed it instead of monospace lines (see `templates/` note).

### Checklist for a clean .docx
- Run with: `timeout 90 /home/jianliu/miniconda3/bin/python -u conv.py`.
- Set CJK fonts: add `w:eastAsia` to each run's rPr (宋体 body, 黑体 headings) so Chinese renders.
- Tables: `doc.add_table()` + `table.style = "Table Grid"`; bold the header row, dark-blue header text.
- Code blocks: monospace runs (Consolas), 9pt, left-indent.
- Blockquotes: indented gray paragraphs.
- Bold `**x**` / inline `` `x` ``: split with `re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)`.
- Verify by re-opening the .docx with python-docx: print paragraph count, each table's rows×cols + header cells.

## 3b. DOCX Extraction
```python
from docx import Document
doc = Document("file.docx")
text = "\n".join(p.text for p in doc.paragraphs)
```

## 4. PDF Split / Merge / Search (pymupdf)
```python
import fitz

# Split: extract pages 2-5
doc = fitz.open("source.pdf")
new = fitz.open()
new.insert_pdf(doc, from_page=1, to_page=5)
new.save("excerpt.pdf")

# Search: find text
for page in doc:
    instances = page.search_for("target text")
    for inst in instances:
        print(f"Found at {inst}")

# Merge
combined = fitz.open()
for f in ["a.pdf", "b.pdf"]:
    combined.insert_pdf(fitz.open(f))
combined.save("combined.pdf")
```

## Pitfalls

- **web_extract** only works for publicly accessible URLs (no auth). For paywalled/authenticated documents, download locally first.
- **marker-pdf** needs 3-5GB disk space for its models. First use takes longer due to model download.
- **nano-pdf** requires valid API key. Page numbering (0- vs 1-based) varies by version — test with a known page first.
- **pymupdf** can't OCR images. Use marker-pdf for scanned documents.
- **DOCX via python-docx** handles .docx only, not .doc. Old .doc files require LibreOffice conversion.
