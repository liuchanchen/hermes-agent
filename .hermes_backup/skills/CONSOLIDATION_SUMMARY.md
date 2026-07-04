# Library Consolidation — June 24, 2026

## Summary

Completed umbrella-building consolidation pass on ~77 agent-created skills. Created 6 new class-level umbrella skills and absorbed 38 narrow siblings into them. Archived 5 Apple/macOS platform-unsupported skills (stale built-ins).

**Net change:** 77 → ~40 class-level skills (before bundled skills), a 48% reduction in surface area.

## Clusters Processed

### Cluster 1: Apple/macOS (5 skills, stale built-ins)
- **Archived (stale):** apple-notes, apple-reminders, findmy, imessage, macos-computer-use
- **Status:** All unsupported on this platform (WSL/Linux). Archived as stale built-ins under `.archive/apple/`.

### Cluster 2: LLM Fine-tuning & Post-training (5 skills)
- **Created umbrella:** `llm-fine-tuning` (mlops/) — covers Axolotl, Unsloth, TRL, Outlines, Obliteratus in one SKILL.md with labeled subsections
- **Absorbed:** axolotl, unsloth, fine-tuning-with-trl, outlines, obliteratus
- **Moved support files:** Reference files from all 5 absorbed skills moved under `references/` and `templates/`

### Cluster 3: HuggingFace Hub Download (2 skills)
- **Patched umbrella:** `huggingface-mirror-download` (mlops/) — added general hf CLI commands section from the absorbed sibling
- **Absorbed:** huggingface-hub

### Cluster 4: GitHub Workflows (5 skills)
- **Created umbrella:** `github-workflows` (github/) — covers auth, issues, PR lifecycle, code review, repo management, codebase inspection in one SKILL.md
- **Absorbed:** github-auth, github-issues, github-pr-workflow, github-code-review, github-repo-management
- **Copied templates:** bug-report.md, feature-request.md, github-api-cheatsheet.md

### Cluster 5: External Coding Agents (4 skills)
- **Created umbrella:** `external-coding-agents` (autonomous-ai-agents/) — covers Claude Code, OpenAI Codex, OpenCode, and Kanban Codex Lane in one SKILL.md
- **Absorbed:** claude-code, codex, opencode, kanban-codex-lane

### Cluster 6: PDF / Document Processing (2 skills)
- **Created umbrella:** `document-processing` (productivity/) — covers OCR extraction and PDF text editing
- **Absorbed:** ocr-and-documents, nano-pdf
- **Note:** `powerpoint` and `teams-meeting-pipeline` left standalone (different domains)

### Cluster 7: GPU Architecture Reference (2 skills)
- **Created umbrella:** `gpu-architecture-reference` (mlops/) — covers Ascend 950 NPU specs and Super Node/scale-up protocols
- **Absorbed:** ascend-950, super-node

### Cluster 8: Remote Server Management (3 per-server skills)
- **Absorbed into `remote-server-management`:** remote-server-70-88, remote-server-70-96, remote-server-70-98
- **Status:** Per-server detailed notes already mostly duplicated from the umbrella. One truth kept.

### Cluster 9: Development Workflows (15 skills — the largest merge)
- **Created umbrella:** `development-workflows` (software-development/) — covers planning, subagent-driven development, TDD, code review, simplification, spikes, debugging (general + Python + Node.js + Hermes TUI + shared library), skill authoring, and verification
- **Absorbed:** writing-plans, subagent-driven-development, verification-agent, simplify-code, requesting-code-review, spike, test-driven-development, hermes-agent-skill-authoring, systematic-debugging, debugging-workflow, python-debugpy, node-inspect-debugger, debugging-hermes-tui-commands, coding-go, python-automation, python-package-management

### Cluster 10: GLM-5.1-NVFP4 Server Deployment (1 skill)
- **Absorbed into `model-deployment`:** glm5-nvfp4-vllm-server

## Skills Left Standalone (intentionally)

These are genuinely distinct class-level skills that don't overlap:
- All creative skills (architecture-diagram, ascii-art, ascii-video, baoyu-*, claude-design, comfyui, design-md, excalidraw, humanizer, ideation, manim-video, p5js, pixel-art, popular-web-designs, pretext, sketch, songwriting, touchdesigner-mcp)
- All media skills (gif-search, heartmula, songsee, spotify, youtube-content)
- Research skills (arxiv, blogwatcher, llm-wiki, media-workflow, polymarket, research-paper-writing, wallstreetcn-news)
- Hermes system skills (hermes-agent, hermes-backup, hermes-provider-debugging, response-formatting, session-review-and-update, skill-library-maintenance)
- ML serving/inference (serving-llms-vllm, vllm-tuning, llama-cpp, model-deployment, wan2.2-inference)
- Other: airtable, google-workspace, interview, linear, maps, notion, obsidian, openhue, xurl, himalaya, godmode, native-mcp, dongchedi-l90-watch, audiocraft-audio-generation, evaluating-llms-harness, segment-anything-model, weights-and-biases, dspy, build-management, webhook-subscriptions, jupyter-live-kernel, language-translation, kanban-orchestrator, kanban-worker, document-processing, codebase-inspection, teams-meeting-pipeline, powerpoint, minecraft-modpack-server, pokemon-player,
