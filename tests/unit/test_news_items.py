"""The mapping rules the adapters share.

They are pure functions, so the cases that no fixture happens to contain — a URL without a host, a
blank candidate, an offset timestamp that lands on the previous day — are pinned here rather than
left to whichever adapter first runs into them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from numenews.models import NewsId
from numenews.news.items import item_text, news_id, publisher_name, utc_date


def test_news_id_is_deterministic_and_url_specific() -> None:
    """The same link keeps its id across runs; a different link gets a different one."""
    url = "https://example.test/a"

    assert news_id(url) == news_id(url)
    assert isinstance(news_id(url), NewsId)
    assert news_id(url) != news_id("https://example.test/b")


def test_publisher_name_prefers_the_first_usable_candidate() -> None:
    """A blank or missing candidate is skipped, and the value is trimmed."""
    assert publisher_name(
        "Example News", "example.com", url="https://x.test/a", fallback="gdelt"
    ) == ("Example News")
    assert publisher_name(None, "  Example News  ", url="https://x.test/a", fallback="gdelt") == (
        "Example News"
    )
    assert publisher_name("   ", None, url="https://x.test/a", fallback="gdelt") == "x.test"


def test_publisher_name_falls_back_to_the_url_host_then_the_adapter() -> None:
    """`source` is never empty: the host answers next, and the adapter name is the last resort."""
    assert publisher_name(None, url="https://news.example.org/world", fallback="gdelt") == (
        "news.example.org"
    )
    assert publisher_name(None, url="not a url", fallback="gdelt") == "gdelt"


def test_item_text_takes_the_first_usable_candidate() -> None:
    """Adapters pass their preference in order; blanks and missing values fall through."""
    assert item_text(None, "  description  ", "content") == "description"
    assert item_text(None, "   ") == ""


def test_utc_date_reads_a_naive_timestamp_as_utc() -> None:
    """GDELT's `Z` parses into a naive datetime, which is already UTC."""
    assert utc_date(datetime(2026, 9, 21, 23, 59, 59)) == date(2026, 9, 21)


def test_utc_date_converts_an_offset_timestamp() -> None:
    """A local time west of UTC can belong to the previous UTC day."""
    local = datetime(2026, 9, 21, 23, 30, tzinfo=timezone(timedelta(hours=-5)))

    assert utc_date(local) == date(2026, 9, 22)
    assert utc_date(datetime(2026, 9, 21, 1, 0, tzinfo=UTC)) == date(2026, 9, 21)
