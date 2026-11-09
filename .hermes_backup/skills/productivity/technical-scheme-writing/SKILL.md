---
name: technical-scheme-writing
description: Write and iterate on technical scheme/proposal documents (方案) in Chinese for hardware/infra engineering — hardware spec tables, compute-ratio derivations, architecture diagrams, datasheet cross-verification, and iterative edit loops delivering to Word. Use when the user asks to write/modify a 方案, scheme, proposal, or spec-backed document covering hardware/LLM-infra/platform design.
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [technical-writing, scheme, proposal, 方案, hardware-specs, cross-verification, docx]
    category: productivity
---

# Technical Scheme / Proposal Writing (方案)

Covers writing and iterating on technical scheme documents in Chinese for
WarpDrive/hardware/LLM-infra engineering: heterogeneous-inference-platform 方案,
hardware selection + compute-ratio tables, architecture/server-layout diagrams,
and the repeated edit loop that ends with a Word deliverable.

For the docx/diagram MECHANICS (markdown→docx, embedding PNGs, headless-Chrome
diagram rendering, the WSL conda-wrapper + named-style gotchas) see the
`document-processing` skill — this skill is about the CONTENT and STRUCTURE.

A concrete worked instance of this class (WarpDrive heterogeneous
inference-platform 方案: TGU card-family specs, chapter skeleton, file layout) is
in `references/warpdrive-inference-platform-scheme.md`. Reuse it as a template
for future hardware/LLM-infra proposals.

## Core flow
1. Gather requirements and the fixed numbers the user asserts (e.g. card compute
   "TGU01-F = 250T FP16, 500T INT8"). Treat user-given specs as ground truth.
2. Research/verify the non-user components from authoritative sources (NVIDIA
   official datasheets, vendor pages). See Verification below.
3. Draft the 方案 with a stable chapter skeleton (§1 background/goals, §2
   hardware selection & ratio, §3 architecture, §4 scheduler/design, §5
   server/network layout, §6 flows, §7 metrics, …). Keep scheduler internals
   abstract unless the user asks for detail — users often want the top-level
   scheme with proprietary scheduler behavior "not expanded".
4. Deliver as markdown first; convert to Word on request via `document-processing`.
5. Expect heavy ITERATION (below).

## Naming / terminology preferences (from repeated corrections in this session)
- Update the TITLE when product names/card names get rebranded: e.g. replace the
  card codename (TGU01-F) with the vendor/product name (曲速自研算力卡), and
  fix ambiguous nationality phrasing (国产非算力卡 → 非国产算力卡). Do this in the
  title AND sweep the body headings so nothing stale remains.
- When the user gives you a card-family table, introduce ALL members — do not
  single one out as "平台主用卡" unless explicitly asked.
- Drop "定位" (positioning) columns, legend/footnote 说明 lines, and reference
  chapters on request — follow the exact scope they specify; don't over-carry.
- Prefer 国产/非国产 (domestic/non-domestic) framing over specific brands when
  both sides are being compared at the pool level.
- INT8/FP16 specs: keep the user's baseline (e.g. 2250T) canonical for ratio
  tables, but DOCUMENT the official-numeric difference explicitly when the
  datasheet figure differs (e.g. B300 rack FP16 ≈2.5 PF dense/sparse ~5 PF vs
  2250T baseline) so the derivation is transparent.

## Claim framing — baselines must be stated explicitly (2026-09-05 correction)
When writing experiment conclusions, EVERY comparative claim must name its
baseline explicitly. The mistake: wrote "瓶颈是 GPU 数量被分成两半" for a PD test
whose baseline was 4-GPU mixed — "halved" implied an 8-GPU baseline that never
existed. Correct framing: "PD used 2× the GPUs (8 vs 4) and still lost". Rule:
- Before writing 变化/损失/提升, ask: compared to WHAT? State the reference
  configuration in the same sentence (卡数、实例规格、TP size).
- Same-spec comparisons (TP4 vs TP4) must say so: "两边实例规格相同".
- Never describe a quantity as 减半/翻倍/减半损失 without its reference point;
  a ratio without an explicit denominator is an unverified claim.

## Verification — multi-source cross-checking (user's hard requirement)
User insists: "多数据源交叉验证，不要写不确定的数据"; a page showing "暂无" does
NOT mean the data is truly absent. So:
- RATIO/COMPUTE numbers: derive from the user's table and show the arithmetic
  (e.g. 1 H200 ≈989T ⇒ ≈4×TGU01-F(250T), ≈2×TGU02-F(500T), ≈5×TGU02-H2(200T),
  ≈10×TGU02-H(100T)). Compute and print the derivation, don't assert it.
- DATASHEETS: pull from the vendor's official datasheet. If only rack-level
  figures exist (e.g. GB300 NVL72 = 72-GPU: 20TB mem / 576TB/s / 130TB/s NVLink),
  derive per-GPU by /72 and LABEL it as derived (≈288GB / ~8TB/s), and flag any
  residual difference vs the scheme baseline in a footnote.
- Mark every figure with its source ("NVIDIA 官方规格", "供应商内部资料") inline near
  the table so a reader can audit it.

## Iterative edit loop (this class of task ALWAYS iterates)
Turn in a doc and the user will come back with a short numbered list of small
edits ("del 图例", "del 定位 column", "add a column", "del chapter 8/9/10",
"image1 has 路由决策 twice near the arrow, del the duplicate"). Handle these:
- Batch ALL edits, then produce ONE new artifact — don't round-trip per edit.
- For docx: keep the source markdown + diagram HTML as the SOURCE OF TRUTH;
  re-run the markdown→docx converter (which auto-embeds images) rather than
  editing the .docx directly.
- "Do not overwrite the current doc, write to a new doc": write v2 as a NEW file
  (bump the version in the filename) and leave the old one untouched.
- For label-dedup style requests ("route decision appears twice near the arrow"): the
  user wants ONE occurrence per arrow line, not a split — put the single label
  between/beside the arrows.
- Remove now-unused CSS rules / columns when you delete the text that used them
  (KISS — keep sources clean).

## Pitfalls
- Don't re-derive user-given numbers and argue with them; use them as baseline.
- Don't leave stale codenames in headings after a title rebrand — sweep the body.
- Don't invent absent datasheet specs; if the official source lacks a metric,
  say so and leave it flagged rather than guessing (user rejects unsure data).
- Word deliverable is the terminal format for this user; markdown is the
  intermediate. Keep both in sync when only the docx needs the diagram images.
