"""The judge, the embeddings and the answer path the ragas metrics need.

Three things live here and nowhere else:

* **the judge** — an OpenAI-compatible chat model wrapped by ragas' ``llm_factory``, so the four
  metrics run structured-output calls through `instructor` with the JSON mode every compatible
  endpoint supports;
* **the embeddings** — an adapter over the project's own local `fastembed` model:
  ``answer_relevancy`` needs vectors, and ``AGENTS.md`` forbids an embedding API, so the adapter is
  the only way to keep that metric local;
* **the answerer** — the eval's own prompt. numenews has no question-answering agent to reuse (its
  four agents extract, connect, forecast and summarise), and adding a fifth product agent for a test
  would be scope creep, so the harness prompts the configured endpoint itself. The decision is
  recorded in ADR 0013 and `docs/EVAL.md`; unlike a product prompt, this one is deliberately not in
  ``src/numenews/agents/prompts.py``.

This module is imported only by ``tests/eval/test_rag.py``: it is the one file that needs `ragas`,
which lives only in ``.venv-eval`` (ADR 0013).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms import llm_factory
from ragas.llms.base import InstructorBaseRagasLLM
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

from numenews.config import Settings
from numenews.embeddings import FastEmbedSmall
from numenews.embeddings.protocol import Embedder

from .harness import EMBEDDING_CACHE_DIR

#: Sent to an endpoint that needs a syntactically valid key but ignores its value (Ollama, vLLM).
#: `numenews.agents.llm.LOCAL_API_KEY` says the same thing, but that module imports `pydantic-ai`,
#: which the eval environment deliberately does not have (ADR 0013).
LOCAL_API_KEY = "not-needed"

#: How many tokens the judge may spend per call. instructor defaults to 1024, which a reasoning
#: model (`deepseek-flash` and friends) exhausts on its hidden reasoning before it writes the JSON —
#: the call then comes back with `finish_reason="length"` and an `IncompleteOutputException`.
MAX_TOKENS = 4096

#: Where the model is told to look: only the numbered contexts, no invented numbers.
ANSWER_INSTRUCTIONS = (
    "You answer questions about a small corpus of news articles. Use only the numbered contexts, "
    "state the numbers they contain, never invent one, and say so when the contexts do not answer "
    "the question. Answer in one or two sentences."
)


class AnswerDraft(BaseModel):
    """The structured answer the eval's endpoint returns."""

    model_config = ConfigDict(strict=True, extra="forbid")

    answer: str


# mypy sees the ragas boundary as `Any` (the override in pyproject.toml, because ragas is installed
# only in `.venv-eval`), and strict mode refuses to subclass an `Any` base; the base is exactly what
# ragas expects a local embedding to subclass.
class FastEmbedRagasEmbedding(BaseRagasEmbedding):  # type: ignore[misc]
    """A ragas embedding over the project's local 384d model.

    ragas' own embedding providers call an API or load `sentence-transformers`; the eval needs
    neither: the vectors that score `answer_relevancy` come from the same `fastembed` weights the
    corpus was embedded with.
    """

    def __init__(self, embedder: Embedder) -> None:
        super().__init__()
        self._embedder = embedder

    def embed_text(self, text: str, **kwargs: object) -> list[float]:
        """Return the vector of one text, synchronously."""
        del kwargs
        return self._embedder.embed([text])[0]

    async def aembed_text(self, text: str, **kwargs: object) -> list[float]:
        """Return the vector of one text, off the event loop (fastembed's `embed` blocks)."""
        del kwargs
        vectors = await asyncio.to_thread(self._embedder.embed, [text])
        return vectors[0]


def endpoint_configured(settings: Settings) -> bool:
    """Return whether an LLM endpoint is configured at all.

    ``build_llm_model`` treats "neither a key nor a base URL" as a configuration error; the eval
    reads the same pair and turns it into a skip, because a machine without an endpoint can still
    run the deterministic half of the suite.
    """
    return settings.openai_api_key is not None or settings.openai_base_url is not None


def build_judge(settings: Settings) -> InstructorBaseRagasLLM:
    """Return the ragas LLM bound to the configured OpenAI-compatible endpoint.

    ``llm_factory`` wraps the client with `instructor` in JSON mode, which is what every
    OpenAI-compatible server (OpenAI, OpenRouter, Ollama, DeepSeek) supports. Only
    :func:`endpoint_configured` callers reach this, so a missing endpoint fails here as a clear
    configuration error rather than as a strange request later.
    """
    api_key = (
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key is not None
        else LOCAL_API_KEY
    )
    client = AsyncOpenAI(
        base_url=str(settings.openai_base_url) if settings.openai_base_url is not None else None,
        api_key=api_key,
    )
    return llm_factory(settings.llm_model, client=client, max_tokens=MAX_TOKENS)


def build_ragas_embeddings() -> FastEmbedRagasEmbedding:
    """Return the local embeddings `answer_relevancy` compares the generated questions with."""
    return FastEmbedRagasEmbedding(FastEmbedSmall(cache_dir=EMBEDDING_CACHE_DIR))


async def generate_answer(
    llm: InstructorBaseRagasLLM,
    question: str,
    retrieved: Sequence[str],
) -> str:
    """Return the eval's answer to ``question`` from the numbered ``retrieved`` contexts."""
    numbered = "\n".join(f"[{index}] {text}" for index, text in enumerate(retrieved, start=1))
    prompt = f"{ANSWER_INSTRUCTIONS}\n\nQuestion: {question}\n\nContexts:\n{numbered}"
    draft = await llm.agenerate(prompt, AnswerDraft)
    return str(draft.answer).strip()


async def score_faithfulness(
    llm: InstructorBaseRagasLLM,
    *,
    question: str,
    response: str,
    retrieved: Sequence[str],
) -> float:
    """Return ragas' `faithfulness`: the share of the answer's claims the contexts support."""
    result = await Faithfulness(llm=llm).ascore(
        user_input=question,
        response=response,
        retrieved_contexts=list(retrieved),
    )
    return float(result.value)


async def score_context_precision(
    llm: InstructorBaseRagasLLM,
    *,
    question: str,
    reference: str,
    retrieved: Sequence[str],
) -> float:
    """Return ragas' `context_precision`: how early the ranked contexts become useful."""
    result = await ContextPrecisionWithReference(llm=llm).ascore(
        user_input=question,
        reference=reference,
        retrieved_contexts=list(retrieved),
    )
    return float(result.value)


async def score_context_recall(
    llm: InstructorBaseRagasLLM,
    *,
    question: str,
    reference: str,
    retrieved: Sequence[str],
) -> float:
    """Return ragas' `context_recall`: how much of the reference the contexts cover."""
    result = await ContextRecall(llm=llm).ascore(
        user_input=question,
        retrieved_contexts=list(retrieved),
        reference=reference,
    )
    return float(result.value)


async def score_answer_relevancy(
    llm: InstructorBaseRagasLLM,
    embeddings: BaseRagasEmbedding,
    *,
    question: str,
    response: str,
) -> float:
    """Return ragas' `answer_relevancy`: how on-topic the answer is for the question."""
    result = await AnswerRelevancy(llm=llm, embeddings=embeddings).ascore(
        user_input=question,
        response=response,
    )
    return float(result.value)


__all__ = [
    "ANSWER_INSTRUCTIONS",
    "MAX_TOKENS",
    "AnswerDraft",
    "FastEmbedRagasEmbedding",
    "build_judge",
    "build_ragas_embeddings",
    "endpoint_configured",
    "generate_answer",
    "score_answer_relevancy",
    "score_context_precision",
    "score_context_recall",
    "score_faithfulness",
]
