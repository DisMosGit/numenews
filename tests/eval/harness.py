"""The evaluated corpus, the retrieval path over it, and the questions that score it.

The eval measures the *production* retriever — :func:`numenews.vector.hybrid_search_news` over real
`fastembed` vectors — so this module rebuilds the two halves the pipeline would normally fill in:
the news items the extract agent would produce (numbers are declared in the fixture, not read by a
model) and the reduced value :func:`numenews.numerology.compute_numerology` gives them.

Nothing here imports `ragas`: the deterministic retrieval test and the ragas metrics share this
module, and only the metrics live behind the eval-only dependency (``tests/eval/judge.py``,
``docs/EVAL.md``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from numenews.embeddings import FastEmbedBase, FastEmbedSmall
from numenews.models import NewsItem
from numenews.news.items import news_id
from numenews.numerology import compute_numerology
from numenews.vector import VectorStore, hybrid_search_news, upsert_news
from numenews.vector.payloads import news_embedding_text

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).parent / "fixtures"
NEWS_FIXTURE = FIXTURES_DIR / "news.jsonl"
QUESTIONS_FIXTURE = FIXTURES_DIR / "questions.jsonl"

#: Where the two bge models are cached. Absolute on purpose (the suite's hermetic ``settings``
#: fixture moves the working directory) and English-only, which is why the corpus is English too:
#: the eval must measure retrieval, not the known language limit of the embedders (`docs/EVAL.md`).
EMBEDDING_CACHE_DIR = REPO_ROOT / ".cache" / "fastembed"

#: How many items one question retrieves; the same list feeds the answer and the ragas contexts.
TOP_K = 5

#: Fraction of questions whose top-`TOP_K` must contain a relevant item for the suite to pass.
HIT_FLOOR = 0.8


class FixtureNews(BaseModel):
    """One line of ``news.jsonl``: an article with the numbers it is known to state."""

    model_config = ConfigDict(strict=True, extra="forbid")

    slug: str
    title: str
    text: str
    source: str
    date: date
    url: str
    numbers: tuple[int, ...]


class EvalQuestion(BaseModel):
    """One line of ``questions.jsonl``: a question, its reference answer and the relevant slugs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    question: str
    reference: str
    relevant: tuple[str, ...]


def load_news(path: Path = NEWS_FIXTURE) -> dict[str, NewsItem]:
    """Return the corpus, keyed by slug, with the production id and reduced value filled in.

    The declared numbers are checked against the text: a fixture whose ``numbers`` list names a
    value that is not written in the article would make the eval claim a reading no extractor could
    have produced, so the loader refuses it instead.

    Raises:
        ValueError: when a slug or URL repeats, a number is not written in the text, or the gematria
            reading is empty (``compute_numerology`` reports ``0`` for text it cannot read).
    """
    rows = [FixtureNews.model_validate_json(line) for line in _lines(path)]
    news: dict[str, NewsItem] = {}
    urls: set[str] = set()
    for row in rows:
        if row.slug in news:
            raise ValueError(f"{path.name}: duplicate slug {row.slug!r}")
        if row.url in urls:
            raise ValueError(f"{path.name}: duplicate url {row.url!r}")
        urls.add(row.url)
        if not row.numbers:
            raise ValueError(f"{path.name}: {row.slug!r} declares no numbers")
        reading = f"{row.title}\n\n{row.text}".strip()
        for number in row.numbers:
            if str(number) not in reading:
                raise ValueError(f"{path.name}: {row.slug!r} does not write {number}")
        value = compute_numerology(reading).value
        if value == 0:
            raise ValueError(f"{path.name}: {row.slug!r} has no readable letters")
        news[row.slug] = NewsItem(
            id=news_id(row.url),
            title=row.title,
            text=row.text,
            source=row.source,
            date=row.date,
            url=row.url,
            numbers=row.numbers,
            numerology_value=value,
        )
    if not news:
        raise ValueError(f"{path.name}: the corpus is empty")
    return news


def load_questions(
    news: Mapping[str, NewsItem],
    path: Path = QUESTIONS_FIXTURE,
) -> list[EvalQuestion]:
    """Return the questions, each checked against the corpus it is scored on.

    Raises:
        ValueError: when an id repeats, a question or reference is blank, or a ``relevant`` slug is
            not in the corpus — a typo in a slug would silently weaken ``context_recall``.
    """
    questions = [EvalQuestion.model_validate_json(line) for line in _lines(path)]
    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            raise ValueError(f"{path.name}: duplicate id {question.id!r}")
        seen.add(question.id)
        if not question.question.strip() or not question.reference.strip():
            raise ValueError(f"{path.name}: {question.id!r} has an empty question or reference")
        if not question.relevant:
            raise ValueError(f"{path.name}: {question.id!r} names no relevant item")
        unknown = [slug for slug in question.relevant if slug not in news]
        if unknown:
            raise ValueError(f"{path.name}: {question.id!r} names unknown slugs {unknown}")
    if not questions:
        raise ValueError(f"{path.name}: there are no questions")
    return questions


def build_store(news: Iterable[NewsItem]) -> VectorStore:
    """Return an in-memory store holding ``news``, embedded with the real local models.

    The eval uses ``QdrantClient(":memory:")`` so it needs no Docker and no ``LD_PRELOAD``
    exemption for localhost, exactly like the integration suite.
    """
    store = VectorStore.in_memory(
        base=FastEmbedBase(cache_dir=EMBEDDING_CACHE_DIR),
        small=FastEmbedSmall(cache_dir=EMBEDDING_CACHE_DIR),
    )
    upsert_news(store, list(news))
    return store


def retrieve(store: VectorStore, question: str, limit: int = TOP_K) -> list[NewsItem]:
    """Return the items the production hybrid search ranks first for ``question``."""
    return hybrid_search_news(store, question, None, limit)


def contexts(items: Iterable[NewsItem]) -> list[str]:
    """Return the text a judge or an answerer is shown for ``items``.

    It is the same string the vector layer embedded (:func:`news_embedding_text`), so a faithfulness
    score cannot be blamed on a difference between what was stored and what was shown.
    """
    return [news_embedding_text(item) for item in items]


def relevant_ids(question: EvalQuestion, news: Mapping[str, NewsItem]) -> set[UUID]:
    """Return the ids the question's ``relevant`` slugs name."""
    return {news[slug].id.root for slug in question.relevant}


def hit(items: Iterable[NewsItem], ids: set[UUID]) -> bool:
    """Return whether any retrieved item is one of ``ids``."""
    return any(item.id.root in ids for item in items)


def _lines(path: Path) -> list[str]:
    """Return the non-empty lines of a JSONL file."""
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


__all__ = [
    "EMBEDDING_CACHE_DIR",
    "FIXTURES_DIR",
    "HIT_FLOOR",
    "NEWS_FIXTURE",
    "QUESTIONS_FIXTURE",
    "REPO_ROOT",
    "TOP_K",
    "EvalQuestion",
    "FixtureNews",
    "build_store",
    "contexts",
    "hit",
    "load_news",
    "load_questions",
    "relevant_ids",
    "retrieve",
]
