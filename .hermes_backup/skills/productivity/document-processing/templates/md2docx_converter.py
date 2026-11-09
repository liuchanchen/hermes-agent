#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown -> DOCX converter (python-docx) that AVOIDS named styles.

Why this shape:
  - The default python-docx template hangs on named-style lookups
    (doc.add_heading, style="List Bullet"/"List Number") deep in
    docx.oxml.xmlchemy — so headings/lists are rendered via direct run
    formatting instead.
  - Run with the DIRECT conda binary on this WSL box because the shell
    `python3` wrapper hangs on a broken conda activation:
        timeout 90 /home/jianliu/miniconda3/bin/python -u this.py

Usage: edit SRC/DST below, or pass src dst as argv.
"""
import re, sys
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.oxml.ns import qn

SRC = sys.argv[1] if len(sys.argv) > 1 else "in.md"
DST = sys.argv[2] if len(sys.argv) > 2 else "out.docx"

def set_east_asia(run, font):
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rf)
    rf.set(qn("w:eastAsia"), font)

def add_run(p, text, bold=False, mono=False, size=None, color=None):
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Consolas" if mono else "Calibri"
    set_east_asia(run, "宋体")
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    return run

def add_inline(p, text):
    for tok in re.split(r"(\*\*.+?\*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            add_run(p, tok[2:-2], bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            add_run(p, tok[1:-1], mono=True)
        else:
            add_run(p, tok)

def add_heading_para(doc, text, level):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(14 if level <= 2 else 8)
    pf.space_after = Pt(6)
    add_run(p, text, bold=True,
            size={1:18, 2:16, 3:14}.get(level, 12),
            color=RGBColor(0x1F, 0x3B, 0x5C))

def parse_table(lines):
    rows = []
    for ln in lines:
        ln = ln.strip().strip("|")
        if re.match(r"^[\s:\-|]+$", ln):
            continue
        rows.append([c.strip() for c in ln.split("|")])
    return rows

def main():
    doc = Document()
    with open(SRC, encoding="utf-8") as f:
        lines = f.read().split("\n")
    i, n, list_counter = 0, len(lines), 0
    while i < n:
        ln = lines[i].rstrip()
        if ln.strip().startswith("```"):
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.5)
                p.paragraph_format.space_after = Pt(0)
                add_run(p, lines[i] if lines[i] else " ", mono=True, size=9)
                i += 1
            i += 1
            doc.add_paragraph()
            continue
        if ln.startswith(">"):
            while i < n and lines[i].strip().startswith(">"):
                q = lines[i].strip()[1:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.75)
                p.paragraph_format.right_indent = Cm(0.25)
                add_inline(p, q)
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
                i += 1
            doc.add_paragraph()
            continue
        if ln.startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:\-|]+\|?\s*$", lines[i+1]):
            tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i]); i += 1
            rows = parse_table(tbl)
            if rows:
                ncols = max(len(r) for r in rows)
                table = doc.add_table(rows=len(rows), cols=ncols)
                table.style = "Table Grid"
                for ri, row in enumerate(rows):
                    for ci in range(ncols):
                        cell = table.cell(ri, ci)
                        cell.text = ""
                        add_inline(cell.paragraphs[0],
                                   row[ci] if ci < len(row) else "")
                        if ri == 0:
                            for r in cell.paragraphs[0].runs:
                                r.bold = True
                                r.font.color.rgb = RGBColor(0x1F, 0x3B, 0x5C)
                doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            add_heading_para(doc, m.group(2), len(m.group(1)))
            i += 1; list_counter = 0; continue
        m = re.match(r"^(\d+)\.\s+(.*)$", ln)
        if m:
            list_counter += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.65)
            p.paragraph_format.first_line_indent = Cm(-0.4)
            add_run(p, f"{list_counter}. ", bold=True)
            add_inline(p, m.group(2)); i += 1; continue
        m = re.match(r"^[-*]\s+(.*)$", ln)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.65)
            p.paragraph_format.first_line_indent = Cm(-0.4)
            add_run(p, "• ", bold=True)
            add_inline(p, m.group(1)); i += 1; continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", ln) or ln.strip() == "":
            i += 1; continue
        add_inline(doc.add_paragraph(), ln); i += 1
    doc.save(DST)
    print("saved:", DST)

if __name__ == "__main__":
    main()
