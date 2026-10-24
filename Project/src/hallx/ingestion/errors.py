"""Typed ingestion failures.

Messages name only field names and failure categories. They never include
source text, file paths, or extracted content.
"""

from __future__ import annotations

from hallx.errors import ErrorCode


class IngestionError(ValueError):
    """A deterministic ingestion failure with a frozen error code."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message


__all__ = ["IngestionError"]
