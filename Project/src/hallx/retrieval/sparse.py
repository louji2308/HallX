"""Deterministic BM25 sparse index over authorized canonical chunk text.

The index is a pure data structure: it never touches the corpus database,
the network, or a model. Construction is order-independent and search ties
break by `chunk_id` ascending, so identical inputs always yield identical
scores and ranks.

Tokenizer `bm25-v1`: casefold the canonical text, then take maximal runs of
Unicode word characters excluding the underscore. Whitespace and punctuation
are separators only; the token stream itself is not stemmed.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from typing import Final

from hallx.models import EvidenceChunk
from hallx.retrieval.bundle import INDEX_VERSION
from hallx.retrieval.errors import RetrievalError, RetrievalErrorCode
from hallx.retrieval.models import ScoredChunk

_TOKEN_PATTERN: Final = re.compile(r"[^\W_]+", re.UNICODE)
_K1: Final = 1.5
_B: Final = 0.75


def tokenize(text: str) -> tuple[str, ...]:
    """Return the fixed token stream for already-canonical text."""

    return tuple(_TOKEN_PATTERN.findall(text.casefold()))


def validate_top_k(top_k: object) -> int:
    """Return a validated positive `top_k` or fail closed."""

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_TOP_K_INVALID,
            "top_k must be a positive integer",
        )
    return top_k


class SparseIndex:
    """An immutable BM25 index built only from the chunks it is given."""

    index_version = INDEX_VERSION

    def __init__(self, chunks: Iterable[EvidenceChunk]) -> None:
        try:
            candidates = tuple(chunks)
        except TypeError as exc:
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_INDEX_INVALID,
                "retrieval chunks must be iterable",
            ) from exc

        seen: set[str] = set()
        for chunk in candidates:
            if not isinstance(chunk, EvidenceChunk):
                raise RetrievalError(
                    RetrievalErrorCode.RETRIEVAL_INDEX_INVALID,
                    "retrieval chunks must be evidence chunks",
                )
            if chunk.chunk_id in seen:
                raise RetrievalError(
                    RetrievalErrorCode.RETRIEVAL_INDEX_INVALID,
                    "retrieval chunks must have unique chunk ids",
                )
            seen.add(chunk.chunk_id)

        ordered = tuple(sorted(candidates, key=lambda chunk: chunk.chunk_id))
        term_frequencies: list[dict[str, int]] = []
        lengths: list[int] = []
        document_frequency: Counter[str] = Counter()
        for chunk in ordered:
            counts = Counter(tokenize(chunk.canonical_text))
            term_frequencies.append(dict(counts))
            lengths.append(sum(counts.values()))
            for term in sorted(counts):
                document_frequency[term] += 1

        document_count = len(ordered)
        total_length = sum(lengths)
        self._chunk_ids: tuple[str, ...] = tuple(chunk.chunk_id for chunk in ordered)
        self._term_frequencies = tuple(term_frequencies)
        self._lengths: tuple[int, ...] = tuple(lengths)
        self._average_length = total_length / document_count if document_count else 0.0
        self._idf: dict[str, float] = {
            term: math.log(
                1.0
                + (document_count - frequency + 0.5) / (frequency + 0.5)
            )
            for term, frequency in sorted(document_frequency.items())
        }

    def __len__(self) -> int:
        return len(self._chunk_ids)

    @property
    def chunk_ids(self) -> tuple[str, ...]:
        return self._chunk_ids

    def search(self, query: str, *, top_k: int) -> tuple[ScoredChunk, ...]:
        if not isinstance(query, str):
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_QUERY_INVALID,
                "query must be a string",
            )
        limit = validate_top_k(top_k)
        tokens = tokenize(query)
        if not tokens:
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_QUERY_INVALID,
                "query must contain at least one searchable token",
            )

        query_frequency = Counter(tokens)
        query_terms = tuple(sorted(query_frequency))
        if self._average_length <= 0.0:
            return ()

        scored: list[tuple[float, str]] = []
        for position, chunk_id in enumerate(self._chunk_ids):
            frequencies = self._term_frequencies[position]
            document_length = self._lengths[position]
            normalization = _K1 * (
                1.0 - _B + _B * document_length / self._average_length
            )
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term)
                if frequency is None:
                    continue
                score += (
                    self._idf[term]
                    * (frequency * (_K1 + 1.0))
                    / (frequency + normalization)
                )
            if score > 0.0:
                scored.append((score, chunk_id))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(
            ScoredChunk(chunk_id=chunk_id, score=score, rank=rank)
            for rank, (score, chunk_id) in enumerate(scored[:limit])
        )


__all__ = ["SparseIndex", "tokenize", "validate_top_k"]
