"""Shared argument checks for deterministic ingestion."""

from __future__ import annotations

from hallx.errors import ErrorCode
from hallx.ingestion.errors import IngestionError


def validate_identifiers(doc_id: str, version_id: str) -> None:
    for value, name in ((doc_id, "doc_id"), (version_id, "version_id")):
        if not isinstance(value, str) or not value.strip():
            raise IngestionError(ErrorCode.SCHEMA_INVALID, f"{name} is required")
        if "\x00" in value:
            raise IngestionError(ErrorCode.SCHEMA_INVALID, f"{name} must not contain NUL")


def validate_chunk_dimensions(max_chars: int, overlap_chars: int) -> None:
    if isinstance(max_chars, bool) or not isinstance(max_chars, int):
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "max_chars must be an integer")
    if isinstance(overlap_chars, bool) or not isinstance(overlap_chars, int):
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "overlap_chars must be an integer")
    if max_chars < 1:
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "max_chars must be positive")
    if overlap_chars < 0:
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "overlap_chars must not be negative")


__all__ = ["validate_chunk_dimensions", "validate_identifiers"]
