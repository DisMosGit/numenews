"""The HTTP layer's decisions that need no transport: what may be cached, and what is a credential.

`tests/integration/test_news_http.py` drives the real client against `respx`, which is what the
retry policy, the status mapping and the cache itself need. The two questions here are pure
functions of a URL or a header, so they are pinned without a network: whether a request
authenticates through its query string — which decides whether hishel may cache it at all — and
whether a response's `Cache-Control` forbids storing it.
"""

from __future__ import annotations

import pytest

from numenews.news.http import _carries_credential

BASE = "https://news.test/v1/search"


def test_a_credential_in_the_query_string_is_recognised() -> None:
    """Mediastack authenticates with `access_key`, so its requests must stay out of the cache."""
    assert _carries_credential(f"{BASE}?access_key=secret") is True


def test_a_credential_after_another_parameter_is_recognised() -> None:
    """The parameter is matched after `&` as well as after `?`, where most traffic puts it."""
    assert _carries_credential(f"{BASE}?q=sun&limit=10&access_key=secret") is True


@pytest.mark.parametrize("parameter", ["access_key", "access_token", "api_key", "apikey", "token"])
def test_every_documented_credential_parameter_is_recognised(parameter: str) -> None:
    """The four header sources document a query parameter as their alternative form, so all of them
    are refused whatever a source switches to."""
    assert _carries_credential(f"{BASE}?q=sun&{parameter}=secret") is True


def test_a_repeated_credential_parameter_is_recognised() -> None:
    """A URL that repeats the parameter is still a request carrying a credential."""
    assert _carries_credential(f"{BASE}?access_key=one&access_key=two") is True


def test_the_parameter_name_is_matched_case_insensitively() -> None:
    """`Access_Key` is the same parameter to a server that reads query strings case-sensitively or
    not, and the cache must not be the place where that difference is discovered."""
    assert _carries_credential(f"{BASE}?Access_Key=secret") is True


def test_an_ordinary_query_string_is_not_a_credential() -> None:
    """GDELT needs no key at all, so its requests keep the cache they have always had."""
    assert _carries_credential(f"{BASE}?query=sun&mode=artlist") is False


def test_a_url_without_a_query_string_is_not_a_credential() -> None:
    """Nothing to authenticate with is nothing to refuse."""
    assert _carries_credential(BASE) is False


def test_a_parameter_that_merely_ends_in_a_credential_name_is_not_a_credential() -> None:
    """`access_key_backup` is another parameter: only a name starting its own parameter counts."""
    assert _carries_credential(f"{BASE}?access_key_backup=notes") is False


def test_a_credential_name_in_a_value_is_not_a_credential() -> None:
    """A query *about* credentials is not a query *carrying* one, so the value is never searched."""
    assert _carries_credential(f"{BASE}?q=access_key%3Dsecret") is False
