"""Source-map facade.

Phase 1 maps canonical spans to original extracted text. PDF page/coordinate
mapping is added in Phase 3 and must use the same canonicalization version.
"""

from __future__ import annotations

from dataclasses import dataclass

from hallx.canonical import CanonicalDocument, canonicalize
from hallx.errors import SourceMapError


@dataclass(frozen=True, slots=True)
class SourceMap:
    document: CanonicalDocument

    @classmethod
    def from_raw(cls, raw_text: str) -> "SourceMap":
        return cls(document=canonicalize(raw_text))

    @property
    def canonicalization_version(self) -> str:
        return self.document.canonicalization_version

    @property
    def canonical_text(self) -> str:
        return self.document.text

    @property
    def sha256(self) -> str:
        return self.document.sha256

    def to_original(self, canonical_start: int, canonical_end: int) -> tuple[int, int]:
        return self.document.to_original_span(canonical_start, canonical_end)

    def to_canonical(self, original_start: int, original_end: int) -> tuple[int, int]:
        return self.document.original_span_to_canonical(original_start, original_end)


__all__ = ["SourceMap", "SourceMapError"]
