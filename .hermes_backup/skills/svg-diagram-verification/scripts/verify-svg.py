#!/usr/bin/env python3
"""Ad-hoc structural/geometry verifier for self-contained SVG/HTML diagrams.

There is no canonical test/lint/build command for hand-written HTML+SVG
diagrams, so run this before calling a diagram "done". It checks structure and
geometry ONLY — it cannot judge aesthetics. For creative/UI work, still let the
user eyeball the rendered result before treating it as final.

Usage:
    python3 verify-svg.py path/to/diagram.html

Exit code 0 = PASS, 1 = FAIL (prints failures to stdout).

Checks:
  - HTML tag balance (no unclosed/mismatched tags)
  - SVG viewBox present; all rects have positive dims and shapes stay in-bounds
  - No <line> endpoint overflows the canvas width (+5px tolerance)
  - No duplicate element IDs
  - Every url(#marker) arrowhead reference resolves to a defined marker
"""
import re
import sys
from html.parser import HTMLParser


class TagChecker(HTMLParser):
    VOID = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr", "rect", "line", "path",
        "circle", "polygon", "marker", "use",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"unexpected </{tag}>")
            return
        top, pos = self.stack.pop()
        if top != tag:
            self.errors.append(f"mismatch <{top}> closed by </{tag}>")


def main(path):
    html = open(path, encoding="utf-8").read()
    issues = []

    tc = TagChecker()
    tc.feed(html)
    if tc.stack:
        issues.append(f"unclosed tags: {[t for t, _ in tc.stack]}")
    issues += tc.errors

    vb = re.search(r'viewBox="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)"', html)
    if not vb:
        issues.append("no viewBox found")
        print("RESULT: FAIL")
        return 1
    x0, y0, w, h = map(float, vb.groups())

    for m in re.finditer(r'<(rect|line|path|circle)[^>]*?x="([\d.]+)"[^>]*?y="([\d.]+)"', html):
        x, y = float(m.group(2)), float(m.group(3))
        if x < x0 - 1 or y < y0 - 1:
            issues.append(f"element at ({x:.0f},{y:.0f}) outside viewBox origin")

    for m in re.finditer(r'<rect[^>]*?width="([\d.-]+)"[^>]*?height="([\d.-]+)"', html):
        if float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
            issues.append("non-positive rect dimensions")

    for m in re.finditer(r'<line[^>]*?>', html):
        if any(float(v) > w + 5 for k, v in re.findall(r'(\w+)="([\d.]+)"', m.group(0)) if k in ("x1", "x2")):
            issues.append("line endpoint overflows canvas")

    ids = re.findall(r'id="([^"]+)"', html)
    dups = {i for i in ids if ids.count(i) > 1}
    if dups:
        issues.append(f"duplicate ids: {dups}")

    refs = re.findall(r'url\(#([^)]+)\)', html)
    missing = [r for r in refs if r not in ids]
    if missing:
        issues.append(f"unresolved marker refs: {missing}")

    print("tag balance:", "OK" if not tc.stack and not tc.errors else "FAIL")
    print(f"viewBox: {x0:.0f},{y0:.0f} {w:.0f}x{h:.0f}")
    print("shapes:", len(re.findall(r'<(rect|line|path|circle)', html)))
    print("dup ids:", dups if dups else "none")
    print("unresolved refs:", missing if missing else "none")
    if issues:
        print("RESULT: FAIL")
        for i in issues:
            print("  -", i)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
