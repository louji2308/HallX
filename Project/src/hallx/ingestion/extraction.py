"""Deterministic text extraction for local sources.

UTF-8 text and Markdown are extracted verbatim. PDF extraction requires a
verified page/coordinate extractor that this build does not include, so PDF
sources return an explicit unsupported-mapping result instead of invented text
or page numbers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from hallx.errors import ErrorCode
from hallx.ingestion.errors import IngestionError
from hallx.ingestion.models import ExtractionResult

TEXT_MEDIA_TYPES = frozenset({"text/plain", "text/markdown", "text/x-markdown"})
PDF_MEDIA_TYPES = frozenset({"application/pdf"})
PDF_UNSUPPORTED_REASON = "no verified PDF text and page-map extractor is available"


def normalize_media_type(media_type: str) -> str:
    if not isinstance(media_type, str) or not media_type.strip():
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "media_type is required")
    return media_type.split(";", 1)[0].strip().lower()


def extract_path(path: str | Path, *, media_type: str) -> ExtractionResult:
    normalized = normalize_media_type(media_type)
    if not isinstance(path, (str, Path)):
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "path must be a string or Path")

    try:
        source_bytes = Path(path).read_bytes()
    except (OSError, ValueError) as exc:
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "source file is not readable") from exc

    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    if normalized in PDF_MEDIA_TYPES:
        return ExtractionResult(
            source_sha256=source_sha256,
            media_type=normalized,
            extraction_text="",
            pages=(),
            unsupported_mapping=True,
            unsupported_reason=PDF_UNSUPPORTED_REASON,
        )

    if normalized not in TEXT_MEDIA_TYPES:
        raise IngestionError(ErrorCode.SCHEMA_INVALID, "media_type is not supported")

    try:
        extraction_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestionError(
            ErrorCode.SCHEMA_INVALID,
            "text source is not valid UTF-8",
        ) from exc

    return ExtractionResult(
        source_sha256=source_sha256,
        media_type=normalized,
        extraction_text=extraction_text,
        pages=(),
        unsupported_mapping=False,
        unsupported_reason=None,
    )


__all__ = [
    "PDF_MEDIA_TYPES",
    "PDF_UNSUPPORTED_REASON",
    "TEXT_MEDIA_TYPES",
    "extract_path",
    "normalize_media_type",
]
