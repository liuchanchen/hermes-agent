# GLM-5.1-NVFP4 `reasoning_effort` — Server-Side Validation Trace

**Date:** 2026-06-08
**Server:** GLM-5.1-NVFP4 on 70.96 (`glm5_1_fp8`, `--reasoning-parser glm45`)
**Method:** Python `urllib.request` POST to `/v1/chat/completions` with `Content-Type: application/json`

---

## Valid Values (HTTP 200)

### `reasoning_effort: 'none'`
- `reasoning`: `null`
- `content`: `"..."` (final answer only — reasoning disabled)
- `finish_reason`: `"length"`

### `reasoning_effort: 'low'`
- `reasoning`: `"1.  **分析输入：** 用户正在询问... 2.  **确定答案：** 1 + 1 = 2。 3.  **构建输出：**..."` (~122 chars)
- `content`: `"1+1等于2。"` ✅ clean final answer
- `finish_reason`: `"stop"`

### `reasoning_effort: 'medium'`
- `reasoning`: Same structure, slightly more detail (~126 chars)
- `content`: `"1+1"` — truncated because reasoning consumed most of 100-token budget
- `finish_reason`: `"length"`

### `reasoning_effort: 'high'`
- `reasoning`: Full step-by-step with context consideration (~320+ chars)
- `content`: `null` — reasoning filled 100-token budget
- `finish_reason`: `"length"`

---

## Invalid Values (HTTP 400)

All return:
```json
{
  "error": {
    "message": "1 validation error: {'type': 'literal_error', 'loc': ('body', 'reasoning_effort'), 'msg': \"Input should be 'none', 'low', 'medium' or 'high'\", 'input': '<VALUE>', 'ctx': {'expected': \"'none', 'low', 'medium' or 'high'\"}}"
  }
}
```

| Tested value | Result |
|---|---|
| `max` | HTTP 400 ❌ |
| `xhigh` | HTTP 400 ❌ |
| `ultra` | HTTP 400 ❌ |
| `off` | HTTP 400 ❌ |
| `minimal` | HTTP 400 ❌ |
| `maximum` | HTTP 400 ❌ |
| `extreme` | HTTP 400 ❌ |

**Source of truth:** `vllm/entrypoints/utils.py` — literal enum check in Pydantic validation.

---

## Key Behavioral Notes

1. **`content: null` at `high` is expected** — not a bug. The model writes its full chain-of-thought into `reasoning`, and with modest `max_tokens` the token budget is exhausted before reaching content output.

2. **`'low'` produces the cleanest chat-format output** — short reasoning + full content in `content` field.

3. **`/v1/completions` (non-chat) bypasses reasoning entirely** — no `reasoning` field, output always in `text`. Use this when you need clean text without thinking traces.

4. **Server-side validation is strict** — the enum is enforced at the vLLM Pydantic layer before any model call. No silent fallthrough.

5. **Independent from Hermes config** — Hermes agent's `reasoning_effort: xhigh` config does NOT affect what values the GLM server accepts. They are separate systems.