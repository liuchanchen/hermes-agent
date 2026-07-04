---
name: development-workflows
description: Software development methodologies and workflows — implementation plans, subagent-driven development, code review, verification, spikes, simplification, TDD, skill authoring, and debugging
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Development, Methodology, Code-Review, TDD, Debugging, Planning, Spikes]
---

# Development Workflows

Umbrella skill for software development methodologies and processes. Covers planning, implementation, code review, testing, debugging, and code maintenance workflows.

## Quick Reference

| Workflow | When to Use | Key Tool |
|----------|-------------|----------|
| **Writing Plans** | Before complex multi-step implementation | `plan` skill (protected) |
| **Subagent SDD** | Executing plans with parallel agents | `delegate_task` |
| **TDD** | Writing new features with tests-first | `test-driven-development` subsection |
| **Code Review** | Pre-commit verification pipeline | `requesting-code-review` subsection |
| **Simplify Code** | After changes, clean up | `simplify-code` subsection |
| **Spike** | Before committing to an unknown approach | `spike` subsection |
| **Debugging** | Root cause analysis for bugs | `systematic-debugging` subsection |
| **Skill Authoring** | Creating SKILL.md files | `hermes-agent-skill-authoring` subsection |
| **Verification** | Independent output validation | `verification-agent` subskill |

---

## 1. Implementation Planning (Writing Plans)

For complex features or refactors with multiple steps, write a plan document:

### Plan structure
```
# Goal
One-line summary

# Approach
High-level strategy

# Tasks (in order)
Each task: 2-5 min, single focused action
- File paths with exact code
- Exact shell commands with expected output
- Verification step

# Risks & Tradeoffs
```

### Task granularity rules
- Each task = single focused action (2-5 min)
- Include exact file paths, copy-pasteable code, commands
- Every task has a verification step
- Principles: DRY, YAGNI, TDD, Frequent Commits

Execute via `subagent-driven-development` (Section 2) or `delegate_task`.

## 2. Task Execution with Subagents

For each task in a plan:
1. **Dispatch implementer** — `delegate_task` with full context
2. **Spec review** — verify requirements met
3. **Quality review** — code quality check
4. **Mark complete** — move to next task

Use fresh subagents per task to prevent context pollution. After all tasks, run full test suite and commit.

## 3. TDD (Test-Driven Development)

### The Iron Law
**No production code without a failing test first.**

### Red-Green-Refactor cycle
1. **RED**: Write a test that fails
2. **GREEN**: Write minimal code to pass
3. **REFACTOR**: Clean up while keeping tests green

### Rules
- Tests must use real code, not mocks
- Must SEE test fail before implementing
- If discipline violated, delete code and restart

## 4. Pre-commit Code Review Pipeline

Full verification before commit:

1. **Get diff**: `git diff main...HEAD`
2. **Static security scan**: grep for secrets, injection patterns
3. **Baseline tests + linting**: run with recorded baseline
4. **Self-review checklist**: correctness, security, quality, testing
5. **Independent subagent review**: `delegate_task` with fail-closed JSON result
6. **Auto-fix loop**: max 2 cycles of fix → re-scrutinize
7. **Commit**: prefix with `[verified]`

## 5. Simplify Code (Post-change Cleanup)

After making changes, run the simplification workflow:

1. **Identify changes**: `git diff main...HEAD`
2. **Parallel 3-agent review**:
   - Agent 1: Code Reuse — find duplication with existing code
   - Agent 2: Code Quality — conventions, naming, architecture
   - Agent 3: Efficiency — performance, complexity
3. **Merge results**: deduplicate, resolve conflicts
4. **Apply fixes**: prioritize readability
5. **Verify**: run full test suite

## 6. Spikes (Throwaway Prototypes)

Before committing to an unfamiliar technology or approach:

1. **Decompose** the idea into 2-5 independent feasibility questions
2. **Order by risk** — most uncertain first
3. **Research** approaches for each question
4. **Build standalone prototypes** in `spikes/NNN-name/` dirs
5. **Close each question** with VERDICT: VALIDATED / PARTIAL / INVALIDATED

Run comparison spikes in parallel via `delegate_task`.

## 7. Debugging

### 4-Phase Root Cause Analysis

**Phase 1: Understand**
- Read error messages completely
- Reproduce the issue
- Check recent changes (`git log --oneline -10`)
- Trace data flow from source

**Phase 2: Isolate**
- Narrow to specific module / input / environment
- Find a working example to compare
- Identify differences between working and broken

**Phase 3: Diagnose**
- Single hypothesis at a time
- Minimal test to confirm or refute
- Rule of 3: after 3 failed fixes, question the architecture

**Phase 4: Fix & Verify**
- Create regression test first
- Apply targeted fix (not scatter-shot)
- Verify the test passes

### Language-specific debugging

#### Python
```python
import pdb; pdb.set_trace()    # Local breakpoint
python -m pdb script.py        # Launch under pdb
```

For remote debugging via debugpy:
```python
import debugpy
debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()
```

#### Node.js
```bash
node inspect script.js                   # CLI REPL
node --inspect-brk script.js             # Chrome DevTools
kill -SIGUSR1 <pid>                      # Attach to running process
```

For headless CDP (chrome-remote-interface):
```bash
npm install chrome-remote-interface
node -e "const CDP = require('chrome-remote-interface')"
```

### Hermes TUI debugging
For slash commands in the TUI (Python + Ink + gateway), the debug path is:
1. Check TUI output (TypeScript → Ink)
2. Check Python `COMMAND_REGISTRY` (source of truth)
3. Check tui_gateway JSON-RPC bridge
4. Fix: add `CommandDef` entries, verify autocomplete data ships from Python
5. Rebuild TUI: `npm run build`

### Shared library debugging
```bash
ldd /path/to/binary | grep "not found"    # Missing libs
LD_DEBUG=files /path/to/binary            # Trace loading
strace -e openat /path/to/binary 2>&1     # File access trace
```

## 8. Skill Authoring

For creating SKILL.md files (in-repo or user-local):

### Required frontmatter
```yaml
---
name: skill-name
description: "<25 word summary of when/who/why this skill helps"
author: <name>
tags: [keyword1, keyword2]
---
```

### Structure
- Overview → When to Use → Body (numbered steps, exact commands) → Pitfalls → Verification Checklist
- Linked files in `references/`, `templates/`, `scripts/`, `assets/`
- In-repo skills go in the repo's `.hermes-skills/` dir

### Constraints
- `description` ≤ 1024 chars
- `name` ≤ 64 chars
- SKILL.md ≤ 100K chars total

## 9. Output Verification

For critical outputs, run an independent verification subagent:

```python
from hermes_tools import delegate_task
result = delegate_task(
    goal="Verify the output meets requirements",
    context=f"User request: {request}\nOutput produced: {output}",
    toolsets=["file", "terminal"],
)
```

The verifier must produce evidence-backed checks ending in `VERDICT: PASS`, `VERDICT: FAIL`, or `VERDICT: PARTIAL`.

## Pitfalls

- **Don't plan without coding**: Planning mode saves to `.hermes/plans/` without executing. Switch to execution after planning.
- **TDD without seeing the red**: If you never saw the test fail, the test isn't testing anything worthwhile.
- **Debugging by guessing**: Always isolate before fixing. Guessing wastes more time than measuring.
- **Spike as production code**: Spikes are throwaway. Never commit spike code to the main branch.
- **Code review without the diff**: Always review the actual diff, not just the summary.
- **Verifier info isolation**: Don't tell the verifier what the expected answer is — they should evaluate the output against the requirements independently.
- **Three-reviewer parallelism**: `simplify-code` dispatches all 3 agents with the full diff. They search independently, so duplicate findings are possible. The parent always deduplicates before applying.
