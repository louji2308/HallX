"""End-to-end deterministic ingestion."""

from __future__ import annotations

from pathlib import Path

from hallx.canonical import CANONICALIZATION_VERSION
from hallx.errors import ErrorCode
from hallx.ingestion._validation import validate_chunk_dimensions, validate_identifiers
from hallx.ingestion.chunking import chunk_extraction
from hallx.ingestion.errors import IngestionError
from hallx.ingestion.extraction import extract_path
from hallx.ingestion.models import IngestionResult


def ingest_path(
    path: str | Path,
    *,
    doc_id: str,
    version_id: str,
    media_type: str,
    max_chars: int = 1200,
    overlap_chars: int = 100,
) -> IngestionResult:
    validate_identifiers(doc_id, version_id)
    validate_chunk_dimensions(max_chars, overlap_chars)

    extraction = extract_path(path, media_type=media_type)
    if extraction.unsupported_mapping:
        raise IngestionError(
            ErrorCode.SOURCE_MAP_UNSUPPORTED,
            "source map is not supported for this source",
        )

    chunks = chunk_extraction(
        extraction,
        doc_id=doc_id,
        version_id=version_id,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    return IngestionResult(
        doc_id=doc_id,
        version_id=version_id,
        source_sha256=extraction.source_sha256,
        canonicalization_version=CANONICALIZATION_VERSION,
        extraction=extraction,
        chunks=chunks,
    )


__all__ = ["ingest_path"]
