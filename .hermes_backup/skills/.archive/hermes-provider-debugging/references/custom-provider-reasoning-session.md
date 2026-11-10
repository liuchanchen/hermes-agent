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

## Root Cause (Original — June 2026)

The reasoning content display is **server-driven, not client-driven** for most
custom providers...

## Profile Path Fix (July 2026 — This Session)

A new wrinkle: depending on how `provider:` is configured, Hermes uses either:

### Legacy path (`provider: custom` with no ProviderProfile match)
- `get_provider_profile("custom")` returned `None` previously
- Code path: `chat_completions.py` legacy flag path (lines 286–493)
- Reasoning: `_supports_reasoning_extra_body()` returns `False`
- DeepSeek branch sends `chat_template_kwargs: {thinking: true, reasoning_effort: "max"}`

### Profile path (`provider: custom` with CustomProfile matched)
- Since `CustomProfile` is registered via `register_provider(custom)` in
  `plugins/model-providers/custom/__init__.py`, `get_provider_profile("custom")`
  **does** return a profile
- Code path: profile path via `_build_kwargs_from_profile()` in `chat_completions.py`
- Reasoning comes from `CustomProfile.build_api_kwargs_extras()`

**The bug (fixed July 2026):** `CustomProfile.build_api_kwargs_extras()` only
handled the **disable** case — when `reasoning_config` has `effort: "none"` or
`enabled: false`, it set `extra_body["think"] = False`. But it **never forwarded**
reasoning parameters when thinking was **enabled**. The function returned empty
`extra_body` and empty `top_level`, effectively dropping the reasoning config
on the floor.

**The fix** (`plugins/model-providers/custom/__init__.py`):

```python
def build_api_kwargs_extras(self, *, reasoning_config=None, **ctx):
    extra_body = {}
    top_level = {}

    if reasoning_config:
        _effort = (reasoning_config.get("effort") or "").strip().lower()
        _enabled = reasoning_config.get("enabled", True)

        if _effort == "none" or _enabled is False:
            extra_body["think"] = False          # disable: unchanged
        else:
            extra_body["think"] = True            # enable: NEW
            if _effort in {"xhigh", "max"}:
                top_level["reasoning_effort"] = "max"
            elif _effort in {"low", "medium", "high"}:
                top_level["reasoning_effort"] = _effort

    return extra_body, top_level                  # top_level used to be always {}
```

Now with `reasoning_effort: xhigh` in config, the profile sends:
```json
{"reasoning_effort": "max", "extra_body": {"think": true}}
```

### Which path is active?

This depends on whether `get_provider_profile("custom")` succeeds. The
`CustomProfile` is registered at import time in
`plugins/model-providers/custom/__init__.py`. If the plugin discovery finds it
(which it does in a standard Hermes checkout), the profile path is used.

To determine which path is active for your setup:
1. Add logging: `logger.info(f"Profile for custom: {get_provider_profile('custom')}")`
2. Or check `hermes logs` with `agent.verbose: true` for `extra_body:` output

## Key Code Locations (Updated)

| File | Key Lines | Purpose |
|------|-----------|---------|
| `run_agent.py` | 4684–4724 | `_supports_reasoning_extra_body()` gate |
| `agent/chat_completion_helpers.py` | 727–811 | API kwargs builder (profile vs legacy dispatch) |
| `agent/transports/chat_completions.py` | 286–493 | Legacy flag path kwargs assembly |
| `agent/transports/chat_completions.py` | 495–634 | Profile path kwargs assembly |
| `agent/transports/chat_completions.py` | 636–711 | `normalize_response()` — reasoning extraction from response |
| `agent/agent_runtime_helpers.py` | 991–1069 | `extract_reasoning()` — unified reasoning text extraction |
| `providers/__init__.py` | 65–73 | `get_provider_profile()` — provider registry lookup |
| `plugins/model-providers/custom/__init__.py` | 19–51 | `CustomProfile.build_api_kwargs_extras()` — custom provider reasoning forwarding |

## Pitfalls

- **Profile vs legacy path confusion**: The `custom` provider has BOTH a
  registered profile (`CustomProfile` in `plugins/model-providers/custom/`)
  AND a legacy fallback. Which one fires depends on whether
  `get_provider_profile("custom")` finds the plugin. Verify with verbose
  logging.
- **`CustomProfile.build_api_kwargs_extras()` was the silent dropper**: Before
  July 2026, this method always returned empty `top_level` dict, meaning
  top-level params like `reasoning_effort` were never sent. Only
  `extra_body["think"]` was set (for the disable case). Check the current code
  if reasoning still doesn't appear.
- **Server-side flags still matter**: Even with correct client-side params,
  the vLLM server must be started with `--enable-reasoning` or equivalent.
  Test with a direct curl to isolate client vs server issues.
