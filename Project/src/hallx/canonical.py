"""Deterministic canonicalization with an explicit source map.

Version `nfkc-ws-v1`:
- every whitespace run collapses to one ASCII space;
- each non-whitespace character is NFKC-normalized in isolation;
- every canonical character carries the original character range it came from.

The map is deliberately conservative. A canonical span can always be mapped
back to a covering original span, or the caller receives a `SourceMapError`.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

from hallx.errors import SourceMapError

CANONICALIZATION_VERSION = "nfkc-ws-v1"


@dataclass(frozen=True, slots=True)
class CanonicalChar:
    """One canonical character and the original range that produced it."""

    original_start: int
    original_end: int


@dataclass(frozen=True, slots=True)
class CanonicalDocument:
    """Canonical text plus its provenance map."""

    raw_text: str
    text: str
    char_map: tuple[CanonicalChar, ...]
    canonicalization_version: str
    sha256: str

    def __post_init__(self) -> None:
        if len(self.char_map) != len(self.text):
            raise ValueError("char_map length must equal canonical text length")

    @classmethod
    def from_raw(cls, raw_text: str) -> "CanonicalDocument":
        if not isinstance(raw_text, str):
            raise TypeError("raw_text must be a string")

        canonical_parts: list[str] = []
        char_map: list[CanonicalChar] = []
        index = 0
        length = len(raw_text)

        while index < length:
            character = raw_text[index]

            if character.isspace():
                run_start = index
                while index < length and raw_text[index].isspace():
                    index += 1
                canonical_parts.append(" ")
                char_map.append(CanonicalChar(original_start=run_start, original_end=index))
                continue

            normalized = unicodedata.normalize("NFKC", character)
            for normalized_character in normalized:
                canonical_parts.append(normalized_character)
                char_map.append(CanonicalChar(original_start=index, original_end=index + 1))
            index += 1

        text = "".join(canonical_parts)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return cls(
            raw_text=raw_text,
            text=text,
            char_map=tuple(char_map),
            canonicalization_version=CANONICALIZATION_VERSION,
            sha256=digest,
        )

    def __len__(self) -> int:
        return len(self.text)

    def to_original_span(self, canonical_start: int, canonical_end: int) -> tuple[int, int]:
        """Map a half-open canonical span to a covering original span.

        Raises `SourceMapError` for invalid or unmappable boundaries.
        """

        self._validate_span(canonical_start, canonical_end)
        first = self.char_map[canonical_start]
        last = self.char_map[canonical_end - 1]
        original_start = first.original_start
        original_end = last.original_end
        if original_start < 0 or original_end <= original_start:
            raise SourceMapError("canonical span maps to an empty original span")
        return original_start, original_end

    def original_span_to_canonical(self, original_start: int, original_end: int) -> tuple[int, int]:
        """Map a half-open original span to the canonical span it covers."""

        if not isinstance(original_start, int) or not isinstance(original_end, int):
            raise SourceMapError("original span boundaries must be integers")
        if original_start < 0 or original_end <= original_start:
            raise SourceMapError("original span must be positive and non-empty")
        if original_end > len(self.raw_text):
            raise SourceMapError("original span exceeds source length")

        indices = [
            position
            for position, entry in enumerate(self.char_map)
            if entry.original_start >= original_start and entry.original_end <= original_end
        ]
        if not indices:
            raise SourceMapError("original span has no canonical representation")
        return indices[0], indices[-1] + 1

    def _validate_span(self, canonical_start: int, canonical_end: int) -> None:
        if not isinstance(canonical_start, int) or not isinstance(canonical_end, int):
            raise SourceMapError("canonical span boundaries must be integers")
        if canonical_start < 0 or canonical_end <= canonical_start:
            raise SourceMapError("canonical span must be positive and non-empty")
        if canonical_end > len(self.text):
            raise SourceMapError("canonical span exceeds canonical text length")


def canonicalize(raw_text: str) -> CanonicalDocument:
    """Canonicalize raw extracted text and build its source map."""

    return CanonicalDocument.from_raw(raw_text)


def digest_text(text: str) -> str:
    """Return the SHA-256 hex digest of UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
