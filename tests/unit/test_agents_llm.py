"""Tests for the LLM client and the layer boundary of `agents` (ROADMAP 4.1).

Nothing here touches the network: the model is only *constructed*, and the endpoint is a fake one.
The same construction is what the pipeline of phase 5 will do with real settings.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import AnyHttpUrl, SecretStr
from pydantic_ai.models.openai import OpenAIChatModel

from numenews.agents import LLMConfigurationError, build_llm_model
from numenews.agents.llm import LOCAL_API_KEY
from numenews.config import Settings


def test_build_llm_model_reads_the_openai_settings(settings: Settings) -> None:
    """Key, model name and the default endpoint are the ones `Settings` carries."""
    configured = settings.model_copy(
        update={"openai_api_key": SecretStr("sk-test"), "llm_model": "gpt-4o-mini"}
    )

    model = build_llm_model(configured)

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-4o-mini"
    assert model.base_url == "https://api.openai.com/v1/"
    assert model.client.api_key == "sk-test"


def test_build_llm_model_uses_a_custom_base_url(settings: Settings) -> None:
    """OpenRouter and other OpenAI-compatible gateways arrive through `OPENAI_BASE_URL`."""
    configured = settings.model_copy(
        update={
            "openai_api_key": SecretStr("sk-or-test"),
            "openai_base_url": AnyHttpUrl("https://openrouter.ai/api/v1"),
            "llm_model": "openai/gpt-4o-mini",
        }
    )

    model = build_llm_model(configured)

    assert model.base_url.rstrip("/") == "https://openrouter.ai/api/v1"
    assert model.model_name == "openai/gpt-4o-mini"
    assert model.client.api_key == "sk-or-test"


def test_build_llm_model_supports_a_keyless_local_endpoint(settings: Settings) -> None:
    """A local Ollama needs no real key, but the OpenAI client refuses to be built without one."""
    configured = settings.model_copy(
        update={
            "openai_base_url": AnyHttpUrl("http://localhost:11434/v1"),
            "llm_model": "llama3.2",
        }
    )

    model = build_llm_model(configured)

    assert model.base_url.rstrip("/") == "http://localhost:11434/v1"
    assert model.client.api_key == LOCAL_API_KEY


def test_build_llm_model_requires_an_endpoint(settings: Settings) -> None:
    """No key and no base URL means there is nothing to talk to, and it says so before any run."""
    with pytest.raises(LLMConfigurationError, match="OPENAI_BASE_URL"):
        build_llm_model(settings)


def _imported_numenews_modules(statement: str) -> set[str]:
    """Return the `numenews` modules loaded after running `statement` in a fresh interpreter.

    A subprocess is needed because the rest of the suite imports the vector and news layers, which
    would otherwise pollute an in-process check.
    """
    program = (
        "import sys\n"
        f"{statement}\n"
        "print(' '.join(sorted(name for name in sys.modules if name.startswith('numenews'))))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    return set(completed.stdout.split())


@pytest.mark.parametrize(
    "banned",
    [
        "numenews.news",
        "numenews.vector",
        "numenews.embeddings",
        "numenews.mcp",
        "numenews.cli",
    ],
)
def test_agents_do_not_import_other_layers(banned: str) -> None:
    """docs/ARCHITECTURE.md: the reasoning layer may import `numerology` and `models` only."""
    assert banned not in _imported_numenews_modules("import numenews.agents")
