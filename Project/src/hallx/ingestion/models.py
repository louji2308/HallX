"""Frozen P3A ingestion models.

The models are intentionally strict: offsets are half-open and must match the
declared text exactly, page ranges must be provable slices of the extraction
text, and a chunk's original text must canonicalize to its canonical text.
No model carries a model-supplied offset.
"""

from __future__ import annotations

from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize

_HEX64 = r"^[0-9a-f]{64}$"
_CHUNK_ID = r"^chk-[0-9a-f]{64}$"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class SourcePage(_FrozenModel):
    page_number: int = Field(ge=1)
    text: str
    extraction_char_start: int = Field(ge=0)
    extraction_char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def _span_matches_text(self) -> SourcePage:
        if self.extraction_char_end <= self.extraction_char_start:
            raise ValueError("extraction_char_end must exceed extraction_char_start")
        if len(self.text) != self.extraction_char_end - self.extraction_char_start:
            raise ValueError("page text length must equal its extraction range")
        return self


class ExtractionResult(_FrozenModel):
    source_sha256: str = Field(pattern=_HEX64)
    media_type: str = Field(min_length=1)
    extraction_text: str
    pages: tuple[SourcePage, ...]
    unsupported_mapping: bool
    unsupported_reason: str | None

    @model_validator(mode="after")
    def _consistent(self) -> ExtractionResult:
        if self.unsupported_mapping:
            if self.unsupported_reason is None or not self.unsupported_reason.strip():
                raise ValueError("an unsupported mapping requires a reason")
        elif self.unsupported_reason is not None:
            raise ValueError("a supported mapping must not carry an unsupported reason")

        page_numbers = [page.page_number for page in self.pages]
        if len(page_numbers) != len(set(page_numbers)):
            raise ValueError("page numbers must be unique")

        for page in self.pages:
            if page.extraction_char_end > len(self.extraction_text):
                raise ValueError("page range exceeds extraction text")
            if (
                self.extraction_text[page.extraction_char_start : page.extraction_char_end]
                != page.text
            ):
                raise ValueError("page text does not match extraction text")

        ordered = sorted(self.pages, key=lambda page: page.extraction_char_start)
        for previous, current in pairwise(ordered):
            if current.extraction_char_start < previous.extraction_char_end:
                raise ValueError("page ranges must not overlap")
        return self


class ChunkDraft(_FrozenModel):
    chunk_id: str = Field(pattern=_CHUNK_ID)
    chunk_index: int = Field(ge=0)
    original_text: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    canonical_char_start: int = Field(ge=0)
    canonical_char_end: int = Field(gt=0)
    original_char_start: int = Field(ge=0)
    original_char_end: int = Field(gt=0)
    page_start: int | None = Field(ge=1)
    page_end: int | None = Field(ge=1)
    source_map_supported: bool
    unsupported_reason: str | None

    @model_validator(mode="after")
    def _consistent(self) -> ChunkDraft:
        if self.canonical_char_end <= self.canonical_char_start:
            raise ValueError("canonical_char_end must exceed canonical_char_start")
        if self.original_char_end <= self.original_char_start:
            raise ValueError("original_char_end must exceed original_char_start")
        if len(self.canonical_text) != self.canonical_char_end - self.canonical_char_start:
            raise ValueError("canonical text length must equal its canonical range")
        if len(self.original_text) != self.original_char_end - self.original_char_start:
            raise ValueError("original text length must equal its original range")
        if (self.page_start is None) != (self.page_end is None):
            raise ValueError("page_start and page_end must be provided together")
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must not precede page_start")
        if self.source_map_supported:
            if self.unsupported_reason is not None:
                raise ValueError("a supported source map must not carry an unsupported reason")
        elif self.unsupported_reason is None or not self.unsupported_reason.strip():
            raise ValueError("an unsupported source map requires a reason")
        if canonicalize(self.original_text).text != self.canonical_text:
            raise ValueError("original_text must canonicalize to canonical_text")
        return self


class IngestionResult(_FrozenModel):
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str
    extraction: ExtractionResult
    chunks: tuple[ChunkDraft, ...]

    @model_validator(mode="after")
    def _consistent(self) -> IngestionResult:
        if not self.doc_id.strip():
            raise ValueError("doc_id is required")
        if not self.version_id.strip():
            raise ValueError("version_id is required")
        if self.canonicalization_version != CANONICALIZATION_VERSION:
            raise ValueError("canonicalization_version is not supported")
        if self.extraction.source_sha256 != self.source_sha256:
            raise ValueError("extraction source hash must match the result source hash")
        if self.extraction.unsupported_mapping and self.chunks:
            raise ValueError("an unsupported extraction must not produce chunks")
        if not self.chunks:
            return self

        canonical = canonicalize(self.extraction.extraction_text)
        previous: ChunkDraft | None = None
        for index, chunk in enumerate(self.chunks):
            if chunk.chunk_index != index:
                raise ValueError("chunk indexes must be contiguous from zero")
            if chunk.canonical_char_end > len(canonical.text):
                raise ValueError("chunk canonical range exceeds canonical text")
            if canonical.text[chunk.canonical_char_start : chunk.canonical_char_end] != (
                chunk.canonical_text
            ):
                raise ValueError("chunk canonical text does not match its canonical range")
            if chunk.original_char_end > len(self.extraction.extraction_text):
                raise ValueError("chunk original range exceeds extraction text")
            if (
                self.extraction.extraction_text[
                    chunk.original_char_start : chunk.original_char_end
                ]
                != chunk.original_text
            ):
                raise ValueError("chunk original text does not match its original range")
            if previous is not None:
                if chunk.canonical_char_start <= previous.canonical_char_start:
                    raise ValueError("chunk canonical starts must strictly increase")
                if chunk.canonical_char_start > previous.canonical_char_end:
                    raise ValueError("chunk canonical ranges must not leave gaps")
                if chunk.canonical_char_end <= previous.canonical_char_end:
                    raise ValueError("chunk canonical ends must strictly increase")
            previous = chunk

        if self.chunks[0].canonical_char_start != 0:
            raise ValueError("the first chunk must start at canonical offset zero")
        if self.chunks[-1].canonical_char_end != len(canonical.text):
            raise ValueError("the last chunk must cover the canonical text end")
        return self


__all__ = ["ChunkDraft", "ExtractionResult", "IngestionResult", "SourcePage"]
