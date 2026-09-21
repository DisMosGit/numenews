"""Deterministic half of the eval: the fixtures load and the production search finds them.

This file needs no LLM, no `ragas` and no key, so it runs everywhere `make test-eval` does —
including the machines where the metric half skips for the want of an endpoint. It fails on the
things that are objectively wrong: a corpus that drifted from its questions, a question whose
relevant items are no longer retrievable.
"""

from __future__ import annotations

import pytest

from numenews.models import NewsItem
from numenews.vector import VectorStore

from .harness import HIT_FLOOR, TOP_K, EvalQuestion, hit, relevant_ids, retrieve

#: The sizes roadmap 9.1 names; a fixture edit that drops or adds an item has to say so here.
CORPUS_SIZE = 50
QUESTION_COUNT = 20


@pytest.mark.eval
def test_corpus_has_the_documented_size(
    eval_news: dict[str, NewsItem],
    eval_questions: list[EvalQuestion],
) -> None:
    """The corpus and the question set are the ones roadmap 9.1 specifies."""
    assert len(eval_news) == CORPUS_SIZE
    assert len(eval_questions) == QUESTION_COUNT


@pytest.mark.eval
def test_retrieval_hit_rate(
    eval_store: VectorStore,
    eval_news: dict[str, NewsItem],
    eval_questions: list[EvalQuestion],
) -> None:
    """At least :data:`~tests.eval.harness.HIT_FLOOR` of the questions retrieve a relevant item.

    The contexts the ragas metrics score are exactly this top-:data:`~tests.eval.harness.TOP_K`
    list, so a miss here is a retrieval regression independent of what any judge thinks of the
    answer.
    """
    missed: list[str] = []
    for question in eval_questions:
        items = retrieve(eval_store, question.question)
        if not hit(items, relevant_ids(question, eval_news)):
            missed.append(question.id)
    rate = (len(eval_questions) - len(missed)) / len(eval_questions)
    assert rate >= HIT_FLOOR, f"hit@{TOP_K} is {rate:.2f}, missed {missed}"
