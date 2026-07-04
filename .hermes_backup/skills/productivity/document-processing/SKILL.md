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

## 3. DOCX Extraction
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
