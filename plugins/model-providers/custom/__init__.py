"""Custom / Ollama (local) provider profile.

Covers any endpoint registered as provider="custom", including local
Ollama instances and OpenAI-compatible reasoning endpoints (GLM-5.2 on
Volcengine ARK, vLLM, llama.cpp). Key quirks:
  - ollama_num_ctx → extra_body.options.num_ctx (local context window)
  - reasoning_config disabled → top-level reasoning_effort="none"
    (Ollama /v1/chat/completions ignores think=False — ollama#14820)
    + extra_body.think = False only on Ollama URLs (/api/chat and proxies)
  - reasoning_config enabled + effort → top-level reasoning_effort
    (the native OpenAI-compatible format GLM/ARK expect; unset omits it
    so the endpoint's server default applies)
  - DeepSeek V4 reasoning → chat_template_kwargs (including Think Max)
  - GLM-5.2 enabled reasoning → chat_template_kwargs Think Max
"""

from typing import Any
from urllib.parse import urlparse

from providers import register_provider
from providers.base import ProviderProfile


def _looks_like_ollama_endpoint(base_url: str | None) -> bool:
    """True when ``base_url`` is an Ollama host, not a generic OpenAI-compat relay.

    ``think`` is an Ollama-native extra_body field. Strict hosts (Mistral
    ``extra=forbid``, Groq, …) reject it with HTTP 422. Match only explicit
    Ollama signatures — default port 11434, or ``ollama`` as a hostname
    label — not arbitrary localhost (llama.cpp / vLLM / LM Studio).
    """
    raw = (base_url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    # urlparse raises ValueError for non-integer / out-of-range ports
    # ("http://host:99999/v1" parses fine in the OpenAI client, so the URL
    # is reachable here). Treat a malformed port as "not Ollama" instead of
    # killing the whole kwargs build — same try/except shape the 11434
    # check in hermes_cli/models.py uses, not the same detection logic.
    try:
        if parsed.port == 11434:
            return True
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    if host == "ollama.com" or host.endswith(".ollama.com"):
        return True
    return "ollama" in host.split(".")


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

        # Reasoning / thinking control for custom OpenAI-compatible endpoints
        # (GLM-5.2 on Volcengine ARK, vLLM, Ollama, llama.cpp, …).
        #
        # GLM-5.2 and DeepSeek V4 on custom vLLM endpoints use
        # chat_template_kwargs. Other endpoints use the generic top-level
        # reasoning_effort contract, plus think=False on Ollama when disabled.
        #
        #   - disabled  → top-level reasoning_effort="none"; extra_body.think
        #     = False only on Ollama URLs (Ollama's thinking-off flag)
        #   - enabled + effort set → top-level reasoning_effort for generic
        #     OpenAI-compatible endpoints
        #   - enabled + no effort  → omit both, so the endpoint applies its own
        #     server-side default (do NOT force a level the user didn't pick).
        #
        # We deliberately do NOT emit ``think=True`` on generic endpoints:
        # it is an Ollama-only flag and thinking is already server-default-on.
        # Mistral/Groq also reject unknown fields (HTTP 422 extra_forbidden),
        # so ``think=False`` stays Ollama-URL-gated.
        if reasoning_config and isinstance(reasoning_config, dict):
            _effort = (reasoning_config.get("effort") or "").strip().lower()
            _enabled = reasoning_config.get("enabled", True)
            _model = "".join(
                char for char in str(ctx.get("model") or "").lower() if char.isalnum()
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
                    extra_body["chat_template_kwargs"] = {"enable_thinking": False}
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
                # Ollama's /v1/chat/completions silently ignores
                # extra_body.think (only /api/chat honours it — ollama#14820)
                # but respects the top-level reasoning_effort field (#25758).
                # Always emit reasoning_effort="none"; only add think=False
                # when the URL is actually Ollama.
                top_level["reasoning_effort"] = "none"
                if _looks_like_ollama_endpoint(ctx.get("base_url")):
                    extra_body["think"] = False
            elif _effort:
                # Clamp the internal ladder onto the widest OpenAI-compatible
                # wire vocabulary (shared policy in agent.reasoning_effort) —
                # GLM/ARK, vLLM and SGLang all top out at "max"; forwarding
                # "ultra" verbatim is a guaranteed 400 (#89503).
                from agent.reasoning_effort import (
                    OPENAI_COMPAT_WIRE_EFFORTS,
                    clamp_effort,
                )

                top_level["reasoning_effort"] = clamp_effort(
                    _effort, OPENAI_COMPAT_WIRE_EFFORTS
                )

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
