"""Unique exact-quote resolution on canonical text."""

from __future__ import annotations

from hallx.errors import ErrorCode, SpanResolutionError


def resolve_unique_quote(canonical_text: str, quote: str) -> tuple[int, int]:
    """Resolve a quote to exactly one half-open canonical span.

    The model never supplies offsets. An empty, missing, or multiply occurring
    quote fails closed with a typed error.
    """

    if not isinstance(canonical_text, str) or not isinstance(quote, str):
        raise SpanResolutionError(ErrorCode.QUOTE_NOT_FOUND, "quote and text must be strings")
    if quote == "":
        raise SpanResolutionError(ErrorCode.QUOTE_EMPTY, "quote is empty")

    start = canonical_text.find(quote)
    if start < 0:
        raise SpanResolutionError(ErrorCode.QUOTE_NOT_FOUND, "quote is not present in the chunk")
    if canonical_text.find(quote, start + 1) >= 0:
        raise SpanResolutionError(
            ErrorCode.QUOTE_AMBIGUOUS, "quote occurs more than once in the chunk"
        )
    return start, start + len(quote)
