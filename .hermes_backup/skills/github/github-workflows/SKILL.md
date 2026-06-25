---
name: github-workflows
description: End-to-end GitHub workflows — authentication, PR lifecycle, code review, issues, repo management, and release management via gh CLI and REST API
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, PR, Code-Review, Issues, Repo-Management, CI/CD, Releases]
---

# GitHub Workflows

Umbrella skill covering the full GitHub workflow lifecycle: authentication setup, issue management, PR creation/review/merge, repository management, releases, and CI automation.

## Quick Reference

| Operation | gh CLI | REST API (curl) |
|-----------|--------|-----------------|
| Auth check | `gh auth status` | `curl -H "Authorization: token $GH_TOKEN" https://api.github.com/user` |
| Open PR | `gh pr create --title "..." --body "..."` | `POST /repos/:owner/:repo/pulls` |
| Review PR | `gh pr review --approve` | `POST /repos/:owner/:repo/pulls/:number/reviews` |
| Merge PR | `gh pr merge --squash` | `PUT /repos/:owner/:repo/pulls/:number/merge` |
| Create issue | `gh issue create --title "..." --body "..."` | `POST /repos/:owner/:repo/issues` |
| Create release | `gh release create v1.0 --notes "..."` | `POST /repos/:owner/:repo/releases` |

---

## 1. Authentication Setup

Choose method in order of preference:

### Method A: gh CLI (preferred)
```bash
gh auth login          # Interactive browser or token flow
gh auth status         # Verify it worked
```

### Method B: HTTPS with PAT
```bash
git config --global credential.helper store
echo "https://$GH_TOKEN:@github.com" > ~/.git-credentials
```

### Method C: SSH keys
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
gh ssh-key add ~/.ssh/id_ed25519.pub
```

A helper script (`scripts/gh-env.sh`) is available to detect and set up the optimal auth method automatically.

## 2. Issues

### Viewing
```bash
gh issue list --label bug --assignee @me --limit 20
gh issue view <number> --comments
```

### Creating
```bash
gh issue create --title "Fix login timeout" --body "..." --label bug --assignee @me
```

See `templates/bug-report.md` and `templates/feature-request.md` for issue body templates.

### Triage workflow
1. List unlabeled issues: `gh issue list --json number,title,labels --jq '.[] | select(.labels|length==0)'`
2. Add labels, assign, comment with triage notes
3. Close with `gh issue close <number> -r "duplicate"` or `-r "not_planned"`

## 3. PR Lifecycle

### Branch → Commits → PR
```bash
git checkout -b fix/login-timeout
# Work, commit with conventional commits
git commit -m "fix(auth): resolve login timeout issue"
git push -u origin fix/login-timeout
gh pr create --title "fix: resolve login timeout" --body "Closes #42" --label bug
```

### CI monitoring (poll until complete)
```bash
gh pr checks <number> --watch
```

### Auto-fix loop (max 3 attempts)
1. `gh run view <run-id> --log` → diagnose failure
2. Fix code → `git commit -m "fix ci"` → `git push`
3. Re-check with `gh pr checks --watch`
4. Repeat up to 3 times

### Merge
```bash
gh pr merge <number> --squash --delete-branch
```

For auto-merge via API: `PUT /repos/:owner/:repo/pulls/:number/merge` with merge method.

## 4. Code Review

### Reviewing local changes
```bash
git diff main...HEAD --stat
git diff main...HEAD | head -200  # Full diff preview
git diff main...HEAD -- '*.py'    # Language-specific
```

### Reviewing a PR
```bash
gh pr checkout <number>           # Fetch the PR branch locally
gh pr diff <number>               # View diff in terminal
```

### Leaving reviews
```bash
# Approve
gh pr review <number> --approve --body "LGTM"

# Request changes
gh pr review <number> -r -b "Please fix the X issue"

# Leave inline comments (via REST API)
curl -X POST -H "Authorization: token $GH_TOKEN" \
  https://api.github.com/repos/:owner/:repo/pulls/:number/comments \
  -d '{"body":"Nit: use constant","commit_id":"SHA","path":"file.py","line":42}'
```

### Review checklist
- [ ] Correctness: logic, edge cases, error handling
- [ ] Security: no injection, hardcoded secrets, path traversal
- [ ] Quality: follows project patterns, no dead code
- [ ] Testing: tests cover the change, existing tests still pass

## 5. Repository Management

### Cloning & creation
```bash
gh repo clone owner/repo
gh repo create my-repo --public --clone
gh repo create my-repo --template owner/template-repo
```

### Forking & syncing
```bash
gh repo fork owner/repo --clone --remote=true
gh repo sync owner/repo --branch main
```

### Branch protection
```bash
# Via REST API
curl -X PUT -H "Authorization: token $GH_TOKEN" \
  https://api.github.com/repos/:owner/:repo/branches/main/protection \
  -d '{"required_status_checks":{"strict":true,"contexts":["continuous-integration"]},"enforce_admins":true}'
```

### Secrets
```bash
gh secret set MY_SECRET --body "value"
# API requires libsodium encryption
```

### Releases
```bash
gh release create v1.0.0 --title "v1.0.0" --notes "Release notes..."
gh release upload v1.0.0 ./build/artifact.zip
gh release download v1.0.0
```

### GitHub Actions
```bash
gh workflow list
gh workflow run build.yml --ref main
gh run view <run-id> --log
```

## 6. Codebase Inspection

For codebase metrics (lines of code, language breakdown, code-vs-comment ratios):

```bash
pip install pygount
pygount --format=summary --folders-to-skip=".git,node_modules,venv,__pycache__,build,dist" .
```

**Critical**: Always exclude `.git`, `node_modules`, `venv` or pygount will hang on large repos.

Output shows: Language, Files, Code Lines, Comment Lines, Empty Lines, Percentage.

## Pitfalls

- **Auth**: `gh auth status` may return OK but token lacks repo scope → double-check with `gh api user`
- **Inline comments**: Must use commit SHA, not branch name, in API requests
- **CI logs**: `gh run view` shows last 100 lines; full logs via `--log-failed` or `--log` with pagination
- **Branch protection**: Enabling via API requires sending ALL rules every time (no partial updates)
- **pygount**: Always skip build/third-party dirs or output is misleading
- **Releases**: Can't re-upload an existing asset with the same filename — delete first
