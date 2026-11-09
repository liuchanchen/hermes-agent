# Diagram rendering for Word: ASCII-art → PNG via headless Chrome

Context: when a markdown doc containing box-drawing ASCII diagrams is converted to
.docx, the diagrams render badly in Word. This is the working recipe for turning
them into crisp embedded images.

## Why ASCII-art diagrams break in Word
Box-drawing glyphs (─ │ ┌ ┐ └ ┘ ┬ ┴) and CJK characters are FULL-WIDTH; ASCII
letters/digits and many symbols are HALF-WIDTH. A diagram hand-aligned for a
monospace editor stops being aligned the moment it hits a proportional/full-width
font, and Word's default CJK line-spacing + shrink-to-fit makes it worse. Trying
to render CJK monospace via a font (e.g. WenQuanYi Zen Hei Mono) still fails on
narrow glyphs like `·` (U+00B7) and `⇄` (U+21C4) which aren't fixed-width — so
the font route is a dead end. The robust fix is NOT to render the ASCII at all.

## Robust approach: redraw as HTML/CSS boxes → screenshot PNG
Redraw the diagram as real HTML elements (div boxes + CSS) where the browser
guarantees alignment, then screenshot with headless Chrome.

### 1. Write the diagram as HTML/CSS
- Use rounded `<div>` boxes with `border`, `background` fills for color
  semantics, and arrows as text (`▼`, `│`) or CSS.
- Use a CJK font stack (`font-family: 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', sans-serif`).
- Build ONE html file per diagram (not one page with anchors — `#fragment`
  screenshots capture the whole page, giving you full-page images you must crop).

### 2. Screenshot with headless Chrome
```bash
google-chrome --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1000,1600 \
  --screenshot=diag.png --virtual-time-budget=2500 "file://$(pwd)/diag.html"
```
- `--force-device-scale-factor=2` doubles resolution (crisp in Word).
- `--virtual-time-budget` waits for fonts/layout.
- window-size must be taller than content; the shot is the full window.

### 3. Auto-crop white margins (content bbox)
The shot includes white space around the content. Crop with PIL to the tight
content box — be careful with the polarity:
```python
from PIL import Image
im = Image.open('diag.png').convert('RGBA')
g = im.convert('L')
dark = g.point(lambda p: 255 if p < 245 else 0)  # NON-white -> white
bbox = dark.getbbox()          # bbox of content
pad = 20
im.crop((max(0,bbox[0]-pad), max(0,bbox[1]-pad), bbox[2]+pad, bbox[3]+pad)).save('diagram_1.png')
```
(Trap: using `p > 250` gives the bbox of the WHITE page, not the content.)

### 4. Embed in the .docx
```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture("diagram.png", width=Inches(6.3))  # fit letter margins
```
In the md→docx converter, sniff each ` ``` ` code block: if it contains
box-drawing chars (`─┌┐└┘│┬┴▼`) and a matching image file exists, embed the
image instead of emitting monospace lines.

## Verification of the result (structural, not aesthetic)
- The .docx OOXML package must contain the images:
  ```python
  import zipfile
  z = zipfile.ZipFile('out.docx')
  media = [n for n in z.namelist() if n.startswith('word/media/') and n.endswith('.png')]
  for m in media: assert z.read(m)[:8] == b"\x89PNG\r\n\x1a\n"
  ```
- Count picture paragraphs: `[i for i,p in enumerate(doc.paragraphs) if p._p.xpath('.//w:drawing')]`.
- Confirm each PNG has the expected color components present (scan pixels for the
  accent RGBs used) — catches blank/missing-render cases without eyeballs.
- Aesthetic quality is the user's call: this is creative/visual work, so verify
  format/embedding but let the user judge the look.

## Gotchas hit in practice
- The shell `python3` hangs on the broken conda wrapper → use the direct binary
  `/home/jianliu/miniconda3/bin/python -u`.
- Chrome `#anchor` screenshots ignore the fragment and dump the whole page → one
  html file per diagram, or crop.
- WenQuanYi Zen Hei Mono (ttc index 2) is a promising CJK-mono font but still
  fails on non-full-width symbols (`·`, `⇄`) — don't go down the font path.

## Iterative diagram editing (the common follow-up flow)
Users almost always iterate on the diagrams after first delivery ("delete the
legend", "remove this small line under the title", "drop the HDR/NDR caption").
Keep the diagram HTML files as the SOURCE OF TRUTH and make each tweak a
cheap re-bake, not a doc rewrite:

1. Edit only the diagram's `diagN.html` (delete the element / its CSS rule).
2. Re-run the render → auto-crop → docx-regenerate pipeline (the md→docx
   converter is already written to embed whichever images exist, so just
   re-invoke it — no doc changes needed).
3. Verify: removed string absent from the HTML, PNG dims shrink as expected,
   docx still a valid package with the images embedded.

Batching: if the user gives several diagram edits at once, apply them ALL to the
HTML sources first, then do ONE render+regenerate pass — don't round-trip per
edit. When removing a caption/subtitle, also delete its now-unused CSS rule so
the source stays clean (KISS). The docx text body may legitimately still contain
terms you removed from an image (e.g. RoCEv2 elsewhere in §5) — only assert
absence when the term was image-only.

## Satisfying the standing "fresh verification" requirement (Hermes hygiene)
When the harness demands fresh passing verification each turn you change a file
(and there's no canonical test/lint/build command), run a focused AD-HOC check as
an OS-safe temp script rather than claiming "fully verified":
- Create it with `tempfile.mkstemp(prefix="hermes-verify-", suffix=".py", dir="/tmp")`,
  write the assertions, run it, then `os.remove(tmp)` — leave no crumbs.
- Target exactly the changed paths (e.g. the `diagN.html` source) PLUS the
  downstream artifacts (rendered PNG dims shrinking on caption removal, docx
  still a valid OOXML with the expected media/). Keep it structural/correctness
  only — "RESULT: PASS" + exit code; this is creative/visual work, so aesthetics
  are the user's call.
- State explicitly it is ad-hoc verification, not suite green.
- Common verifier failures to preempt: leaving out `import os` breaks the script
  instantly (NameError); flip PIL crop polarity to the DARK bbox; assert PNG magic
  bytes (`\x89PNG\r\n\x1a\n`) and count `word/media/*.png`.

