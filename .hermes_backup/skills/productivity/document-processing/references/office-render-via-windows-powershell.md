# Render Office files to images via Windows PowerPoint (WSL host)

Context: on WSL/Conda hosts, LibreOffice (`soffice`) is often NOT installed and can't be
`sudo apt`-installed (no root / no password). The default `soffice --convert-to pdf` +
`pdftoppm` render path is then unavailable, which blocks visual QA of .pptx/.docx.
If the Windows host under WSL has MS Office, render a faithful preview through the
Windows COM automation surface instead. PowerPoint-driven export has higher fidelity
for branded templates (e.g. MiSans/Xiaomi) than soffice.

Use this as a drop-in alternative whenever you need a rendered image of an Office doc
for inspection and soffice is missing.

## Prereqs
- Windows host with PowerPoint: `/mnt/c/Program Files/Microsoft Office/root/Office16/POWERPNT.EXE`
- WSL can invoke `powershell.exe` and reach `/mnt/c/...` (WSL absolute paths under /mnt/c work directly).

## Steps

1. Stage the file on a Windows path:
   ```bash
   cp /home/.../out.pptx /mnt/c/Users/<U>/Documents/tgump/
   ```

2. Write `export_ppt.ps1` with `write_file` (NOT inline `-Command` — see pitfall):
   ```powershell
   $ErrorActionPreference = "Stop"
   $src    = "C:\Users\<U>\Documents\tgump\out.pptx"
   $outDir = "C:\Users\<U>\Documents\tgump\render"
   New-Item -ItemType Directory -Force -Path $outDir | Out-Null
   $ppt  = New-Object -ComObject PowerPoint.Application
   $pres = $ppt.Presentations.Open($src, $true, $false, $false) # readonly, notitle, nowindow
   $pres.Export($outDir, "PNG", 2000, 1125)   # width, height in px
   $pres.Close(); $ppt.Quit()
   Write-Output "EXPORT DONE"
   ```

3. Run, then copy PNGs back to WSL:
   ```bash
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\<U>\Documents\tgump\export_ppt.ps1'
   cp "/mnt/c/<U>/Documents/tgump/render/幻灯片1.PNG" ./qa_slide1.png
   ```
   Exported files are named `幻灯片N.PNG` ("Slide N" in Chinese) regardless of host locale.

## Pitfalls
- **Do NOT inline via `powershell.exe -Command "..."` when the script uses `$_`** — bash
  expands `$_` to the previous command's last arg, corrupting the script. Always write the
  `.ps1` with `write_file`, then call it with `-File`.
- COM export opens PowerPoint invisibly; always `Close`/`Quit` the objects, else orphan
  POWERPNT.exe processes linger on the Windows side.

## Inspecting the render when NO vision model is reachable
If every configured model is text-only (auxiliary vision + all custom endpoints report
"is not a multimodal model"), `vision_analyze` and `browser_vision` both fail. Do NOT
loop on them. Fall back to pixel/geometry QA:

- **Theme-color coverage**: downscale the render, sample pixels, assert the expected fill
  colors appear in expected regions (e.g. 6 blue card pixels, 2 amber, navy chassis on a
  server diagram). Confirms cards/topology rendered in place.
- **Ink-ratio heuristic for "text vs tofu"**: crop a text band and count dark pixels.
  Real glyphs give ~5–30% dark ink with varied row distribution (max/avg row-ink > ~1.5).
  Tofu boxes are uniform rectangles with near-constant row ink.
- **Geometry audit beats guessing**: enumerate shapes with python-pptx and check
  (a) every shape within slide bounds, (b) intended centering invariants (e.g. a group
  label's center_x equals its card group's center), (c) no unintended cross-section
  collisions. Distinguish intentional "text-on-own-card" overlaps from real bugs by area
  threshold + container-internal smarts.

In practice the geometry audit caught two real layout bugs (a flow chip colliding with an
adjacent panel, and group pills off-center from their card groups) that a casual glance at
the render could miss — always run it even when you can see the image.
