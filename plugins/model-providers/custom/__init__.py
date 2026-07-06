"""Custom / Ollama (local) provider profile.

Covers any endpoint registered as provider="custom", including local
Ollama instances. Key quirks:
  - ollama_num_ctx → extra_body.options.num_ctx (local context window)
  - reasoning_config disabled → extra_body.think = False
  - DeepSeek V4 reasoning → chat_template_kwargs (including Think Max)
  - GLM-5.2 enabled reasoning → chat_template_kwargs Think Max
  - other enabled reasoning → extra_body.think + top-level reasoning_effort
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class CustomProfile(ProviderProfile):
    """Custom/Ollama local provider — think=false and num_ctx support."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        ollama_num_ctx: int | None = None,
        **ctx: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        # Ollama context window
        if ollama_num_ctx:
            options = extra_body.get("options", {})
            options["num_ctx"] = ollama_num_ctx
            extra_body["options"] = options

        # Reasoning config — DeepSeek V4 exposes its custom Think Max mode
        # through the chat template, not the standard OpenAI-compatible
        # top-level reasoning_effort field.  vLLM validates the latter before
        # rendering the template and rejects "max" there.
        if reasoning_config and isinstance(reasoning_config, dict):
            _effort = (reasoning_config.get("effort") or "").strip().lower()
            _enabled = reasoning_config.get("enabled", True)
            _model = "".join(
                char
                for char in str(ctx.get("model") or "").lower()
                if char.isalnum()
            )

            # GLM-5.2 defaults to Think Max.  Select it explicitly whenever
            # Hermes thinking is enabled, and use the chat-template switch
            # prescribed by vLLM when thinking is disabled.
            if "glm52" in _model:
                _thinking = _enabled is not False and _effort != "none"
                if _thinking:
                    extra_body["chat_template_kwargs"] = {
                        "enable_thinking": True,
                        "reasoning_effort": "max",
                    }
                else:
                    extra_body["chat_template_kwargs"] = {
                        "enable_thinking": False
                    }
                return extra_body, top_level

            if "deepseekv4" in _model:
                _thinking = _enabled is not False and _effort != "none"
                template_kwargs: dict[str, Any] = {"thinking": _thinking}
                if _thinking:
                    if _effort in {"xhigh", "max"}:
                        template_kwargs["reasoning_effort"] = "max"
                    elif _effort in {"low", "medium", "high"}:
                        template_kwargs["reasoning_effort"] = _effort
                extra_body["chat_template_kwargs"] = template_kwargs
                return extra_body, top_level

            if _effort == "none" or _enabled is False:
                # Disable thinking
                extra_body["think"] = False
            else:
                # Enable thinking
                extra_body["think"] = True
                if _effort in {"xhigh", "max"}:
                    top_level["reasoning_effort"] = "max"
                elif _effort in {"low", "medium", "high"}:
                    top_level["reasoning_effort"] = _effort

        return extra_body, top_level

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Custom/Ollama: base_url is user-configured; fetch if set."""
        if not (base_url or self.base_url):
            return None
        return super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)


custom = CustomProfile(
    name="custom",
    aliases=(
        "ollama",
        "local",
        "vllm",
        "llamacpp",
        "llama.cpp",
        "llama-cpp",
    ),
    env_vars=(),  # No fixed key — custom endpoint
    base_url="",  # User-configured
    # Without this, no max_tokens is sent and Ollama falls back to its internal
    # num_predict=128, truncating responses after a few tokens (#39281). This is
    # only a floor used when the user hasn't set model.max_tokens — they can
    # override per-model — so we set it generously rather than lowballing it.
    default_max_tokens=65536,
)

register_provider(custom)
