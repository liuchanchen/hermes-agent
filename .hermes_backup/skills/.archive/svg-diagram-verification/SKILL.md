---
name: svg-diagram-verification
description: "Structurally verify hand-written SVG/HTML diagrams (architecture diagrams, layouts, flowcharts) when no canonical test command exists. Use before delivering any self-contained HTML/SVG artifact."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [verification, svg, html, diagrams, qa]
    related_skills: [architecture-diagram, excalidraw]
---

# SVG / HTML Diagram Verification

Hand-written SVG/HTML diagram artifacts (architecture diagrams, server layouts,
flowcharts) have **no canonical test/lint/build command**. Before delivering
one, run an ad-hoc structural verifier so you can honestly claim "renders
safely" instead of only "I wrote a file."

## When to use

- After producing any self-contained `.html` file with an inline `<svg>`
  via `write_file`.
- Whenever a creative/visual deliverable needs a verification pass and there
  is no project test suite.
- Paired with the `architecture-diagram` / `excalidraw` skills — this is the
  verification half of that workflow.

## Important scope disclaimer

This verifier checks **structure and geometry ONLY**. It cannot judge
aesthetics (colors, spacing taste, visual balance). For creative/UI work,
still let the user eyeball the rendered result before treating it as final.

## How to run

A ready-to-run script lives at `scripts/verify-svg.py`:

```bash
python3 scripts/verify-svg.py path/to/diagram.html
# exit 0 = PASS, 1 = FAIL (prints failures)
```

If the script is not yet copied next to the working dir, use the pattern below
to create your own copy under `/tmp`.

## What it checks

| Check | Catches |
|-------|---------|
| HTML tag balance | unclosed / mismatched tags from hand-writing |
| `viewBox` exists & in-bounds | shapes placed outside the canvas origin |
| positive rect dims | zero/negative width-height typos |
| line endpoints within canvas | arrows/lines drawn off-canvas |
| no duplicate element `id`s | broken `url(#id)` refs / marker collisions |
| marker refs resolve | arrowheads pointing at nonexistent markers |

## Verification-with-proper-evidence pattern

When the environment insists on fresh, explicit verification evidence (a
`hermes-verify-` tempfile pass), use this exact shape so output is attributable:

```python
import os, sys, tempfile, subprocess, textwrap
# put the verifier source in a string ...

fd, tmp = tempfile.mkstemp(prefix="hermes-verify-", suffix=".py", dir="/tmp")
os.close(fd)
with open(tmp, "w", encoding="utf-8") as f:
    f.write(textwrap.dedent(VERIFIER))
r = subprocess.run([sys.executable, tmp, target], capture_output=True, text=True)
print(r.stdout, end=""); print("exit_code:", r.returncode)
os.remove(tmp)                       # always clean up
print("temp_cleaned_up:", not os.path.exists(tmp))
sys.exit(r.returncode)               # propagate real result
```

Key habits:
- `tempfile.mkstemp(prefix="hermes-verify-", dir="/tmp")` — OS-safe path + required prefix.
- **Clean up the tempfile and any wrapper** and echo `temp_cleaned_up: True`.
- Propagate the verifier's real exit code — don't swallow it.
- **Do NOT run linters/tests on creative/UI work before the user says they like it** — hold the aesthetic judgment for the user; verify structure in the meantime.

## Done condition

Only claim a diagram is "verified" when:
1. The verifier passed (exit 0) with the checks above, AND
2. You have explicitly labeled it *ad-hoc verification, not suite green* (there is no suite), AND
3. You have noted the aesthetic/visual pass is still the user's call.

## Related notes

- `references/bot-wall-research-fallback.md` — research-discovery fallback that
  often precedes diagram work: when general search engines are bot-walled, use
  the source's own site search (esp. arXiv) and extract paper sections via
  `browser_console` on the `arxiv.org/html/{id}` page.

## Pitfalls

- Report the pass honestly as "ad-hoc verification (no canonical suite exists)", never as "tests green".
- If the SVG has no `viewBox`, the script fails fast — add one; inline SVGs need it to scale.
- SVG void elements (`rect`, `line`, `path`, `circle`, `polygon`, `marker`) must be in the parser's void set or tag-balance will false-positive — the shipped script already handles this.
