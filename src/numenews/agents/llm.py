"""The OpenAI-compatible model the three agents run on.

Any endpoint that speaks the OpenAI *chat completions* API works: OpenAI itself, OpenRouter, a local
Ollama or vLLM. :class:`~pydantic_ai.models.openai.OpenAIChatModel` is deliberate — the bare
``"openai:"`` model string would select the newer Responses API, which the third-party compatible
servers do not implement. The reasoning behind the choice is in ``docs/adr/0004``.
"""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from numenews.agents.errors import LLMConfigurationError
from numenews.config import Settings, get_settings

#: Key sent to an endpoint that needs one syntactically but ignores its value (Ollama, vLLM).
#: The OpenAI SDK refuses to build a client without a key, and pydantic-ai substitutes a similar
#: placeholder on its own; spelling it out here keeps the behaviour independent of the ambient
#: ``OPENAI_API_KEY`` in the process environment.
LOCAL_API_KEY = "not-needed"


def build_llm_model(settings: Settings | None = None) -> OpenAIChatModel:
    """Return the chat-completions model described by ``settings``.

    ``settings`` defaults to the process-wide :func:`numenews.config.get_settings`, so a caller that
    has no reason to override them does not have to pass anything.

    Args:
        settings: Validated settings to read ``llm_model``, ``openai_base_url`` and
            ``openai_api_key`` from.

    Returns:
        A model bound to the configured endpoint, ready to hand to a ``pydantic_ai.Agent``.

    Raises:
        LLMConfigurationError: If neither a base URL nor an API key is configured — there is no
            endpoint to talk to, and failing here beats failing at the first request.
    """
    resolved = settings if settings is not None else get_settings()
    if resolved.openai_api_key is None and resolved.openai_base_url is None:
        raise LLMConfigurationError(
            "No LLM endpoint configured: set OPENAI_API_KEY (OpenAI, OpenRouter, …) or "
            "OPENAI_BASE_URL (a local server such as Ollama at http://localhost:11434/v1) in the "
            "environment or in `.env`. See docs/PROMPTS.md."
        )

    api_key = (
        resolved.openai_api_key.get_secret_value()
        if resolved.openai_api_key is not None
        else LOCAL_API_KEY
    )
    provider = OpenAIProvider(
        base_url=str(resolved.openai_base_url) if resolved.openai_base_url is not None else None,
        api_key=api_key,
    )
    return OpenAIChatModel(resolved.llm_model, provider=provider)
