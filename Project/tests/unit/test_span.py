import pytest

from hallx.errors import ErrorCode, SpanResolutionError
from hallx.validation.span import resolve_unique_quote


def test_unique_quote_resolves() -> None:
    assert resolve_unique_quote("The rule applies.", "rule") == (4, 8)


def test_missing_quote_fails_closed() -> None:
    with pytest.raises(SpanResolutionError) as caught:
        resolve_unique_quote("The rule applies.", "exception")
    assert caught.value.code is ErrorCode.QUOTE_NOT_FOUND


def test_ambiguous_quote_fails_closed() -> None:
    with pytest.raises(SpanResolutionError) as caught:
        resolve_unique_quote("The rule applies. The rule applies.", "The rule applies.")
    assert caught.value.code is ErrorCode.QUOTE_AMBIGUOUS


def test_empty_quote_fails_closed() -> None:
    with pytest.raises(SpanResolutionError) as caught:
        resolve_unique_quote("The rule applies.", "")
    assert caught.value.code is ErrorCode.QUOTE_EMPTY
