"""Shared builders for P3 ingestion tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from hallx.ingestion import ExtractionResult, SourcePage


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def write_text(
    tmp_path: Path,
    name: str,
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    return write_bytes(tmp_path, name, text.encode(encoding))


def expected_chunk_id(
    doc_id: str,
    version_id: str,
    chunk_index: int,
    canonical_text: str,
) -> str:
    payload = f"{doc_id}\x00{version_id}\x00{chunk_index}\x00{canonical_text}"
    return "chk-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def extraction_with_pages(
    page_texts: tuple[str, ...],
    *,
    media_type: str = "text/plain",
) -> ExtractionResult:
    text = "".join(page_texts)
    pages: list[SourcePage] = []
    cursor = 0
    for page_number, page_text in enumerate(page_texts, start=1):
        pages.append(
            SourcePage(
                page_number=page_number,
                text=page_text,
                extraction_char_start=cursor,
                extraction_char_end=cursor + len(page_text),
            )
        )
        cursor += len(page_text)
    return ExtractionResult(
        source_sha256=sha256_bytes(text.encode("utf-8")),
        media_type=media_type,
        extraction_text=text,
        pages=tuple(pages),
        unsupported_mapping=False,
        unsupported_reason=None,
    )


__all__ = [
    "expected_chunk_id",
    "extraction_with_pages",
    "sha256_bytes",
    "write_bytes",
    "write_text",
]
