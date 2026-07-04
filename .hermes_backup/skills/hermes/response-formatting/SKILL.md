---
name: response-formatting
description: Governs output style, tone, density, and meta-commentary rules across all interactions.
---

# Response Formatting

User preferences for how Hermes formats, structures, and explains outputs.

## Core Rules

1. **Terse, actionable statements.** No meta-commentary ("I think", "I recommend", "Let me check", "I see", "Great question"). State facts and actions directly.
2. **No self-references.** Don't say "I did X" or "I noticed Y." Just do it and output the result.
3. **No formatting flourishes** unless explicitly requested. Plain text > markdown tables > decorative elements.
4. **When user says "just give the answer"** — drop ALL explanation, including rationale. Literally just the answer.
5. **When user says "you always do X and I hate it"** — treat as a hard rule, not a suggestion. Apply immediately and permanently.
6. **Progress reports during multi-step operations:** One line per step, status only. No commentary about what the next step will be — just execute and report.

## User Preferences / Style

### Output Brevity
- Deliver only the actionable output: no preamble, no quotation marks, no justification, no ending remarks. Just the result, command, or file content.
- If multiple items are needed, list them plain, one per line or as a raw block.
- The user actively rejects explanatory commentary, markdown formatting, and verbose responses.

### No Meta-Discussion
- Do not ask "got it?" or "ready to proceed?" or explain why you are doing something. Execute silently and present the minimal deliverable.
- No self-references ("I think", "I recommend", "I did X"). State facts and actions directly.

### Response Format for Decisions / Summaries
- Keep to flat text. Avoid bullet lists, bold, or code fences unless the output is a code snippet.
- When the output is a text-only answer, just write the text.

### Workflow Correction Handling
- When the user corrects a style or process, embed the correction into the relevant skill immediately via `skill_manage(action='patch')`, rather than treating it as a one-off memory item.
- The update must be structural (change SKILL.md body), not a conversational note.

### Skill Update Request Format
- When responding to skill library update requests, use structured `<skill_update>` blocks with clear `<action>`, `<skill_name>`, and `<changes>` sections.
- Changes should be organized by section (pitfalls, steps, format, triggers) with concise `<content>`.

## Pitfalls

- A single sentence of unsolicited explanation is too much.
- "Let me explain why" is never welcome.
- When providing code output, just show the output. No prefaces.
- Don't respond with "got it" or "done" without providing the actual output the user asked for.
- When asked to review and update skill library, be ACTIVE and decisive. Do not default to "nothing to save". Most sessions produce at least one skill update opportunity.
- Prioritize user corrections about style/tone/format/verbosity as FIRST-CLASS skill signals, not just memory items. Update the relevant skill immediately rather than noting it for later.
- When the user wants skills updated, do it proactively. Do not wait for confirmation or ask "would you like me to update?" — just update and explain the change.
