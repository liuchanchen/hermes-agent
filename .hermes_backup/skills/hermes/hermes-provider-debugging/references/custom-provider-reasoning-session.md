# Custom Provider Reasoning Diagnostics

Session notes from debugging why thinking/reasoning content showed for some
custom providers but not the DeepSeek V4 Flash endpoint.

## The Setup

Three custom providers in `~/.hermes/config.yaml`:

```yaml
custom_providers:
- name: 192.168.12.12:51653
  base_url: http://192.168.12.12:51653/v1
  model: deepseekv4-flash        # MiniMax-hosted DeepSeek
- name: 192.168.12.12:19258
  base_url: http://192.168.12.12:19258/v1
  model: deepseekv4-flash        # Primary DeepSeek V4 Flash vLLM
- name: 10.10.70.96:8000
  base_url: http://10.10.70.96:8000/v1
  model: glm5_1_fp8              # GLM-5.1-FP8
- name: 10.10.70.95:8000
  base_url: http://10.10.70.95:8000/v1
  model: minimax_m2_7            # MiniMax-M2.7
```

Model: `deepseekv4-flash`, provider: `custom`, `reasoning_effort: xhigh`,
`show_reasoning: true`.

## Observations

- **GLM-5.1-FP8** and **MiniMax-M2.7**: thinking/reasoning content showed
  correctly in Hermes output
- **DeepSeek V4 Flash** (both endpoints): no thinking content displayed

## Root Cause

The reasoning content display is **server-driven, not client-driven** for most
custom providers:

1. **`_supports_reasoning_extra_body()` returns False** for all custom providers
   (non-OpenRouter base_url hits line 4707: `return False`). This means the
   OpenRouter-style `extra_body["reasoning"]` signal is NEVER sent for custom
   providers.

2. **The DeepSeek branch exists** at line 444–456: when `is_custom_provider=True`
   and the model name contains "deepseek", Hermes sends:
   ```json
   {"chat_template_kwargs": {"thinking": true, "reasoning_effort": "max"}}
   ```
   Whether the vLLM server honors this depends on server configuration.

3. **Server-side thinking**: GLM-5.1 and MiniMax-M2.7 inference stacks
   inherently return `reasoning_content` in the API response regardless of
   client request parameters. DeepSeek V4 Flash on vLLM may not — it might
   require `--enable-reasoning` server flag or a different parameter format.

4. **Hermes extraction** (`extract_reasoning` in `agent_runtime_helpers.py`)
   picks up `reasoning_content` from the API response. If the server doesn't
   return it, no amount of client-side config will make it appear.

## Key Code Path

```
build_api_kwargs()
  → get_provider_profile("custom") returns None
  → Legacy flag path (line 767+)
  → is_custom_provider=True (line 797)
  → supports_reasoning=False (line 806, from _supports_reasoning_extra_body())
  → chat_completions.py line 418: supports_reasoning check = False, skipped
  → chat_completions.py line 444: is_custom_provider = True
    → reasoning_config present, effort="xhigh"
    → "deepseek" in model_lower → True
    → sends chat_template_kwargs with thinking=True, reasoning_effort="max"
  → Server may or may not honor it
```

## Debugging Method Used

- Traced through `_supports_reasoning_extra_body()` in `run_agent.py`
- Traced through `build_kwargs()` in `chat_completions.py` both legacy and profile paths
- Checked `extract_reasoning()` in `agent_runtime_helpers.py`
- Compared behavior across three custom providers to isolate cause

## Verified Findings (curl-confirmed, June 2026)

### DeepSeek V4 Flash at 192.168.12.12:19258

**curl test** (with `chat_template_kwargs: {thinking: true, reasoning_effort: "max"}`):

```json
"message": {
  "role": "assistant",
  "content": "We start with the problem: 2 + 2.",
  "reasoning": null
}
```

✅ Hermes sends `chat_template_kwargs` correctly
❌ Server returns `"reasoning": null` — no thinking content at all
❌ Content is plain string, no structured blocks, no inline ` think...` tags

**Verdict**: This vLLM server instance was started without `--enable-reasoning` or similar flag. The model checkpoint or tokenizer config doesn't produce thinking output regardless of request parameters.

### MiniMax M2.7 at 10.10.70.95:8000

**curl test** (no extra_body, vanilla request):

```json
"message": {
  "role": "assistant",
  "content": " thinkingThe user is asking a simple math question...\n\n...\n response\n\n2+2 = 4",
  "reasoning": null,
  "reasoning_content": null
}
```

❌ `"reasoning": null` — no structured `reasoning` field
❌ `"reasoning_content": null` — no structured `reasoning_content` field
✅ Content contains inline ` thinking...` tags — Hermes extracts via regex fallback
✅ `system_fingerprint: "vllm-0.6.0.dev0-tp8-ep-..."` — this is an older vLLM build

**Verdict**: This vLLM 0.6.0.dev0 server embeds thinking directly in the content string between special tags rather than using structured API fields. Hermes catches this via the inline pattern extraction in `extract_reasoning()`:
```python
r" think(.*?) response"
```

### GLM-5.1-FP8 at 10.10.70.96:8000

Not retested this session, but known from prior work: returns `reasoning_content` as a structured field or content-as-list with `"type": "thinking"` blocks.

### Why This Matters

Each of these three "thinking-capable" custom providers uses a **different format** to communicate reasoning to the client:

| Provider | Reasoning Format | How Hermes Extracts It |
|----------|-----------------|----------------------|
| DeepSeek V4 Flash (19258) | None (unless server configured) | N/A |
| MiniMax M2.7 (95:8000) | Inline ` think...` tags in content | Regex fallback |
| GLM-5.1-FP8 (96:8000) | Structured `reasoning_content` or typed content blocks | Direct field or content-as-list parser |

All three use `provider: custom` with no registered `ProviderProfile`, so Hermes sends NO OpenRouter-style `extra_body["reasoning"]` signal. The DeepSeek branch sends `chat_template_kwargs` but the server may or may not act on it. These three prove that **thinking display for custom providers depends entirely on the server's response format**, not Hermes request configuration.
