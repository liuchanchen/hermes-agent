---
name: hermes-provider-debugging
description: "Debug Hermes Agent provider behavior — reasoning transport, response parsing, custom provider routing, extra_body injection, and understanding why providers behave differently."
version: 1.0.0
---

# Hermes Provider Debugging

Debug Hermes Agent behavior across different providers — especially custom
OpenAI-compatible endpoints. This skill covers the internals of how Hermes
sends requests, signals reasoning, and parses responses, so you can diagnose
why a provider doesn't behave as expected.

## When to Use

- A custom provider endpoint connects and responds but **no thinking/reasoning
  content shows** in the output
- Two custom providers with similar config behave **differently** (one shows
  thinking, the other doesn't)
- You need to understand **what extra_body** Hermes sends to a specific provider
- You're adding a new custom provider (via `custom_providers` in config.yaml)
  and want to verify reasoning signals are sent correctly
- **`display.show_reasoning: true` is set** but reasoning still doesn't display
- The model returns thinking content as inline tags (` think...`) instead of
  structured fields — and you want to verify Hermes extracts it

## Architecture Overview

Hermes has two code paths for building API request kwargs:

### 1. Provider Profile Path (known providers)

Used when the provider has a registered `ProviderProfile` in `providers/` or
`plugins/model-providers/<name>/`. This is the modern path used by OpenRouter,
Anthropic, OpenAI Codex, Nous Portal, GitHub Models, LM Studio, etc.

- Entry: `get_provider_profile(provider_name)` → profile found
- Transport: `_build_kwargs_from_profile()` in `chat_completions.py`
- Reasoning comes from `profile.build_api_kwargs_extras()` + `profile.build_extra_body()`

### 2. Legacy Flag Path (unknown / custom providers)

Used when `get_provider_profile()` returns `None` — i.e., the provider name is
not registered. This is the path for `provider: custom` with a
`custom_providers` entry.

- Entry: `agent/chat_completion_helpers.py` line 767+ (`is_custom_provider=True`)
- Transport: `build_kwargs()` in `chat_completions.py` lines 286–634

## Reasoning Signal Flow

### `_supports_reasoning_extra_body()`

Defined in `run_agent.py` (~line 4684). Returns `True` only for:

1. **Nous Portal** — base_url contains `nousresearch.com`
2. **GitHub Models** — base_url contains `models.github.ai` or `api.githubcopilot.com`
   AND the model supports reasoning
3. **LM Studio** — model has non-"off" reasoning options
4. **OpenRouter** — base_url contains `"openrouter"` AND model starts with a
   known reasoning prefix: `deepseek/`, `anthropic/`, `openai/`, `x-ai/`,
   `google/gemini-2`, `google/gemma-4`, `qwen/qwen3`, `tencent/hy3-preview`,
   `xiaomi/`

**Key rule (line 4707):** If `"openrouter"` is NOT in `_base_url_lower`, the
function returns `False` immediately (after the OpenRouter check). This means
**all custom providers get `supports_reasoning=False`**.

### What `supports_reasoning=False` means for the Legacy Path

Line 418 in `chat_completions.py`:
```python
if params.get("supports_reasoning", False) and not params.get("is_lmstudio", False):
    # ... adds extra_body["reasoning"] with effort
```

Since `supports_reasoning=False` for custom providers, this block is skipped.

### The Custom Provider DeepSeek Branch (Legacy Path)

Lines 444–456 handle custom providers specifically:

```python
if params.get("is_custom_provider", False):
    if reasoning_config and isinstance(reasoning_config, dict):
        _effort = (reasoning_config.get("effort") or "").strip().lower()
        _enabled = reasoning_config.get("enabled", True)
        if _effort == "none" or _enabled is False:
            extra_body["think"] = False
        elif "deepseek" in model_lower:
            _ds_effort = "max" if _effort == "xhigh" else _effort
            extra_body["chat_template_kwargs"] = {
                "thinking": True,
                "reasoning_effort": _ds_effort,
            }
```

This adds `chat_template_kwargs` for any model whose name contains "deepseek".
Whether the vLLM/endpoint server honors this depends on the server implementation.

### What `extra_body_additions` Does

If you configure `extra_body_additions` in the provider profile or pass it via
params, it's merged into `extra_body` at line 479 / 596. This is the escape
hatch for providers that need custom parameters.

## Why Thinking Shows on Some Custom Providers But Not Others

### Case 1: Provider returns reasoning content server-side (GLM-5.1, MiniMax-M2.7)

These inference stacks produce `reasoning_content` in the API response
**regardless of what the client sends in the request**. Hermes's
`_extract_reasoning()` function picks this up from:

1. `assistant_message.reasoning` — DeepSeek/Qwen field
2. `assistant_message.reasoning_content` — Moonshot AI / MiniMax field
3. `assistant_message.reasoning_details` — OpenRouter unified format
4. `assistant_message.content` as a list of typed blocks with `"type": "thinking"`
   — DeepSeek V4 Pro format
5. Inline ` thinking...` or `<thinking>...</thinking>` tags in content text
   — fallback

### Case 2: Provider requires client to request thinking (DeepSeek V4 Flash on vLLM)

The server only returns `reasoning_content` if the client requests it properly.
Hermes sends `chat_template_kwargs` with `thinking: True`, but whether the vLLM
server honors this depends on:

- The **vLLM version** and **model configuration** (some vLLM builds use
  `enable_reasoning` server-side flag instead)
- Whether the **chat template** is configured to handle `chat_template_kwargs`
- Whether the **server is started with `--enable-reasoning`** or equivalent flag

## Response Parsing

`normalize_response()` in `ChatCompletionsTransport` (line 636+) handles:

- `reasoning` — direct field on assistant message
- `reasoning_content` — alternative field (also checked in `model_extra`)
- `reasoning_details` — OpenRouter array format
- These are preserved in `provider_data` for downstream extraction

`extract_reasoning()` in `agent/agent_runtime_helpers.py` (line 991+) then:
1. Checks `reasoning` field
2. Checks `reasoning_content` field (deduplicates)
3. Checks `reasoning_details` array
4. Checks content-as-list with `"type": "thinking"` blocks (DeepSeek V4 Pro)
5. Falls back to inline pattern extraction from content string

## Debugging Steps

When thinking/reasoning content doesn't show for a custom provider:

1. **Enable verbose logging** — set `agent.verbose: true` and check the
   hermes log for `extra_body:` output to see what Hermes sends

2. **Check what the server returns** — send a test curl request:

   ```bash
   curl -s http://<base_url>/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "<model_name>",
       "messages": [{"role": "user", "content": "think about 1+1 step by step"}],
       "extra_body": {"chat_template_kwargs": {"thinking": true, "reasoning_effort": "max"}}
     }' | python3 -m json.tool
   ```

   Check if the response contains `reasoning_content`, `reasoning`, or content
   with `"type": "thinking"` blocks.

3. **Check the code path**:
   - Is `get_provider_profile(provider)` returning a profile? Check
     `providers/` and `plugins/model-providers/`
   - If yes: `_build_kwargs_from_profile()` is used — check
     `profile.build_api_kwargs_extras()` for reasoning handling
   - If no: legacy flag path — verify `is_custom_provider=True` is sent
     (requires `agent.provider == "custom"`)

4. **Check `display.show_reasoning`** — this config option controls whether
   reasoning is displayed in output. Without it, reasoning is extracted but
   not shown.

5. **Check requesting override** — if `request_overrides` contain `extra_body`
   entries, they are merged last and can override reasoning parameters.

## Key Code Locations

| File | Key Lines | Purpose |
|------|-----------|---------|
| `run_agent.py` | 4684–4724 | `_supports_reasoning_extra_body()` gate |
| `agent/chat_completion_helpers.py` | 727–811 | API kwargs builder (profile vs legacy dispatch) |
| `agent/transports/chat_completions.py` | 286–493 | Legacy flag path kwargs assembly |
| `agent/transports/chat_completions.py` | 495–634 | Profile path kwargs assembly |
| `agent/transports/chat_completions.py` | 636–711 | `normalize_response()` — reasoning extraction from response |
| `agent/agent_runtime_helpers.py` | 991–1069 | `extract_reasoning()` — unified reasoning text extraction |
| `providers/__init__.py` | 65–73 | `get_provider_profile()` — provider registry lookup |

## Pitfalls

- **Custom providers get `supports_reasoning=False`** — the gate at line 4707
  returns False for any non-OpenRouter base_url. The custom-provider DeepSeek
  branch at line 450 compensates but only for models whose name contains
  "deepseek". For other custom providers (GLM, MiniMax, etc.), no extra_body
  reasoning signal is sent — they rely on the server returning it unprompted.
- **`extra_body_additions`** is the manual override for custom providers that
  need specific parameters sent in the request body. If reasoning still doesn't
  show after checking the server response, configure `extra_body_additions` in
  the custom provider config.
- **vLLM `--enable-reasoning` flag** — some vLLM deployments require the server
  to be started with `--enable-reasoning` flag for the model to produce thinking
  output, regardless of what the client sends.
- **`chat_template_kwargs` may be silently ignored** by vLLM servers depending
  on the version and model configuration. Testing with a direct curl is the
  fastest way to diagnose this.
