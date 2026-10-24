"""Canonical chunking with stable IDs and provable source ranges."""

from __future__ import annotations

import hashlib

from hallx.canonical import CanonicalDocument, canonicalize
from hallx.errors import ErrorCode
from hallx.ingestion._validation import validate_chunk_dimensions, validate_identifiers
from hallx.ingestion.errors import IngestionError
from hallx.ingestion.models import ChunkDraft, ExtractionResult

_CHUNK_PREFIX = "chk-"


def _chunk_id(doc_id: str, version_id: str, chunk_index: int, canonical_text: str) -> str:
    payload = f"{doc_id}\x00{version_id}\x00{chunk_index}\x00{canonical_text}"
    return _CHUNK_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_safe_boundary(document: CanonicalDocument, index: int) -> bool:
    if index <= 0 or index >= len(document.text):
        return True
    return (
        document.char_map[index - 1].original_end <= document.char_map[index].original_start
    )


def _fit_end(document: CanonicalDocument, start: int, limit: int) -> int:
    end = limit
    while end > start and not _is_safe_boundary(document, end):
        end -= 1
    if end > start:
        return end

    end = limit
    total = len(document.text)
    while end < total and not _is_safe_boundary(document, end):
        end += 1
    if end <= start:
        raise IngestionError(
            ErrorCode.CANONICALIZATION_MISMATCH,
            "unable to choose a canonical chunk boundary",
        )
    return end


def _prefer_whitespace(document: CanonicalDocument, start: int, end: int) -> int:
    floor = start + max(1, (end - start) // 2)
    candidate = end
    while candidate > floor:
        if not _is_safe_boundary(document, candidate):
            candidate -= 1
            continue
        if document.text[candidate - 1].isspace() or (
            candidate < len(document.text) and document.text[candidate].isspace()
        ):
            return candidate
        candidate -= 1
    return end


def _page_range(
    extraction: ExtractionResult,
    original_start: int,
    original_end: int,
) -> tuple[int | None, int | None]:
    overlapping = tuple(
        page
        for page in extraction.pages
        if page.extraction_char_start < original_end
        and page.extraction_char_end > original_start
    )
    if not overlapping:
        return None, None
    return (
        min(page.page_number for page in overlapping),
        max(page.page_number for page in overlapping),
    )


def chunk_extraction(
    extraction: ExtractionResult,
    *,
    doc_id: str,
    version_id: str,
    max_chars: int = 1200,
    overlap_chars: int = 100,
) -> tuple[ChunkDraft, ...]:
    """Split canonical extraction text into stable, provable chunks.

    ``overlap_chars`` is an upper bound: progress requires at least one new
    canonical character per chunk.
    """

    validate_identifiers(doc_id, version_id)
    validate_chunk_dimensions(max_chars, overlap_chars)
    if not isinstance(extraction, ExtractionResult):
        raise IngestionError(
            ErrorCode.SCHEMA_INVALID,
            "extraction must be an ExtractionResult",
        )
    if extraction.unsupported_mapping:
        raise IngestionError(
            ErrorCode.SOURCE_MAP_UNSUPPORTED,
            "source map is not supported for this source",
        )

    canonical = canonicalize(extraction.extraction_text)
    if not extraction.extraction_text or not canonical.text.strip():
        return ()

    total = len(canonical.text)
    chunks: list[ChunkDraft] = []
    start = 0
    chunk_index = 0
    while start < total:
        limit = min(start + max_chars, total)
        end = _fit_end(canonical, start, limit)
        if end < total:
            end = _prefer_whitespace(canonical, start, end)

        canonical_text = canonical.text[start:end]
        original_start, original_end = canonical.to_original_span(start, end)
        original_text = extraction.extraction_text[original_start:original_end]
        if canonicalize(original_text).text != canonical_text:
            raise IngestionError(
                ErrorCode.CANONICALIZATION_MISMATCH,
                "chunk source map does not round-trip",
            )
        page_start, page_end = _page_range(extraction, original_start, original_end)

        chunks.append(
            ChunkDraft(
                chunk_id=_chunk_id(doc_id, version_id, chunk_index, canonical_text),
                chunk_index=chunk_index,
                original_text=original_text,
                canonical_text=canonical_text,
                canonical_char_start=start,
                canonical_char_end=end,
                original_char_start=original_start,
                original_char_end=original_end,
                page_start=page_start,
                page_end=page_end,
                source_map_supported=True,
                unsupported_reason=None,
            )
        )

        if end >= total:
            break
        start = max(end - overlap_chars, start + 1)
        chunk_index += 1

    return tuple(chunks)


__all__ = ["chunk_extraction"]
