---
name: external-coding-agents
description: Delegate coding to external CLI coding agents — Claude Code (Anthropic), Codex (OpenAI), OpenCode (open-source), and Kanban Codex Lane integration
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Coding-Agents, Claude-Code, Codex, OpenCode, Delegation]
---

# External Coding Agents

Delegate coding work to external CLI coding agents. This umbrella skill covers all supported agents: Claude Code, OpenAI Codex, OpenCode, and Hermes Kanban Codex Lane.

## Quick comparison

| Feature | Claude Code | Codex | OpenCode |
|---------|-------------|-------|----------|
| Provider | Anthropic (Claude) | OpenAI (GPT) | Any (OpenRouter etc.) |
| One-shot mode | `-p` (print, prefers stdin) | `exec <prompt>` (PTY) | `run <prompt>` |
| Interactive mode | PTY via tmux | PTY (interactive CLI) | TUI background session |
| Requires git repo | No | **Yes** | No (read tasks) |
| Cost minimum | $0.05/task | N/A | N/A |
| PR review | Yes (parallel) | Yes (batch) | Yes |
| Session resume | `--resume` | Companion script | Background session |
| npm package | `@anthropic-ai/claude-code` | `@openai/codex` | `opencode` |

---

## 1. Claude Code

### Installation
```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### One-shot mode (preferred — non-interactive)
```bash
claude -p "Add unit tests for src/auth.ts" --print
```

For streaming JSON output:
```bash
claude -p "Analyze this file" --print --json --output-format json
```

### Interactive mode (PTY via tmux)
```bash
tmux new -s claude-session
claude
# Ctrl+C to stop, tmux detach to background
```

### PR review
```bash
claude -p "Review this PR diff: $(gh pr diff <number>)" --print
```

### MCP integration
Configure MCP servers in the Claude Code MCP config file to give it access to additional tools.

## 2. OpenAI Codex

### Installation
```bash
npm install -g @openai/codex
codex --help
```

### Usage
```bash
codex exec "Add a JWT auth middleware to the Express app"
```

**Important**: Codex requires being inside a git repo. It also requires a PTY for interactive operations.

### Session continuity
Use the companion script `scripts/codex_session.sh` to maintain ongoing conversations:
```bash
./codex_session.sh start
./codex_session.sh continue "Now add error handling"
```

### Parallel tasks with git worktrees
```bash
git worktree add ../repo-fix-branch fix/branch
cd ../repo-fix-branch && codex exec "Fix the bug" --git-worktree
```

## 3. OpenCode

### Installation
```bash
npm install -g opencode
opencode --version
```

### One-shot
```bash
opencode run "Refactor this function to use async/await"
```

### Interactive background session
```bash
opencode
# Inside the TUI: Ctrl+S to save, Ctrl+D to exit
opencode continue  # Resume session
```

Provider-agnostic — configure via `opencode.json` with OpenRouter, Anthropic, etc.

**Pitfalls**: `/exit` is NOT a valid command — use Ctrl+C to exit.

## 4. Kanban Codex Lane (Hermes Kanban)

When a Hermes Kanban worker needs to delegate implementation to Codex CLI:

1. Hermes **always owns the lifecycle** — Codex is an isolated lane only
2. Use git worktree isolation for safety
3. Structure prompts with explicit constraints
4. Monitor with timeout (default 10 min)
5. Hermes independently reviews the diff AND runs tests after Codex finishes

### Prompt structure for Kanban Codex lane
```
Task: <description>
Source branch: <branch>
Files to modify: <paths>
Constraints:
- Do NOT modify tests/
- Do NOT change package.json
Safety: Read-only in config/
```

## Pitfalls

- **PTY required**: Both Codex and interactive Claude Code need a pseudo-terminal (`pty=true` in terminal tool)
- **Git requirement**: Codex refuses to run outside a git repo. OpenCode doesn't have this restriction for read-only tasks.
- **CLI path**: On some systems, `bun` installs binaries to different paths. Check with `which codex` or `which claude`.
- **Cost**: Claude Code charges per task ($0.05 minimum). Track budgets carefully for batch operations.
- **Kanban Codex Lane**: Always keep the worktree branch separate from main dev branch. Hermes reconciliation must pass before merging.
