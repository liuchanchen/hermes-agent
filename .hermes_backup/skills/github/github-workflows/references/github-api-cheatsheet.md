# GitHub API Cheatsheet

## Common endpoints
- `GET /user` — current user info
- `GET /repos/:owner/:repo` — repo info
- `GET /repos/:owner/:repo/contents/:path` — file contents
- `GET /repos/:owner/:repo/pulls` — list PRs
- `GET /repos/:owner/:repo/pulls/:number/files` — PR changed files
- `POST /repos/:owner/:repo/pulls/:number/reviews` — submit review
- `POST /repos/:owner/:repo/pulls/:number/comments` — inline PR comment
- `GET /repos/:owner/:repo/issues` — list issues
- `PATCH /repos/:owner/:repo/issues/:number` — update issue
- `POST /repos/:owner/:repo/releases` — create release
- `PUT /repos/:owner/:repo/branches/:branch/protection` — branch protection

## Common query params
- `?state=open|closed|all` — PR/issue state
- `?per_page=100` — max results per page (default 30)
- `?page=2` — pagination
- `?sort=created&direction=desc` — sort order

## Pagination via Link header
```bash
curl -sI "https://api.github.com/repos/owner/repo/issues?per_page=100" \
  -H "Authorization: token $GH_TOKEN" | grep -i link
```
