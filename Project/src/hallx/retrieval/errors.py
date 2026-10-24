"""Typed fail-closed errors for ACL-first sparse retrieval.

Messages are bounded: they never include raw query text or chunk text. A
retrieval failure is never repaired and never falls back to an unfiltered
candidate set.
"""

from __future__ import annotations

from enum import Enum


class RetrievalErrorCode(str, Enum):
    RETRIEVAL_QUERY_INVALID = "RETRIEVAL_QUERY_INVALID"
    RETRIEVAL_SNAPSHOT_INVALID = "RETRIEVAL_SNAPSHOT_INVALID"
    RETRIEVAL_TOP_K_INVALID = "RETRIEVAL_TOP_K_INVALID"
    RETRIEVAL_AS_OF_INVALID = "RETRIEVAL_AS_OF_INVALID"
    RETRIEVAL_CONFLICT_INVALID = "RETRIEVAL_CONFLICT_INVALID"
    RETRIEVAL_INDEX_INVALID = "RETRIEVAL_INDEX_INVALID"
    RETRIEVAL_TENANT_MISMATCH = "RETRIEVAL_TENANT_MISMATCH"


class RetrievalError(Exception):
    """A fail-closed retrieval error with a bounded, non-content message."""

    def __init__(self, code: RetrievalErrorCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message


__all__ = ["RetrievalError", "RetrievalErrorCode"]
