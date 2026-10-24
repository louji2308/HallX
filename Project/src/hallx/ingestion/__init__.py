"""Deterministic local ingestion, canonical chunking, and source maps."""

from hallx.ingestion.chunking import chunk_extraction
from hallx.ingestion.errors import IngestionError
from hallx.ingestion.extraction import (
    PDF_MEDIA_TYPES,
    PDF_UNSUPPORTED_REASON,
    TEXT_MEDIA_TYPES,
    extract_path,
    normalize_media_type,
)
from hallx.ingestion.models import ChunkDraft, ExtractionResult, IngestionResult, SourcePage
from hallx.ingestion.service import ingest_path

__all__ = [
    "PDF_MEDIA_TYPES",
    "PDF_UNSUPPORTED_REASON",
    "TEXT_MEDIA_TYPES",
    "ChunkDraft",
    "ExtractionResult",
    "IngestionError",
    "IngestionResult",
    "SourcePage",
    "chunk_extraction",
    "extract_path",
    "ingest_path",
    "normalize_media_type",
]
