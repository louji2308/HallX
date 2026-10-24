"""ACL-first deterministic retrieval into a frozen evidence bundle.

Ordering is the security property, not an implementation detail:

1. validate the request shape without touching the corpus;
2. ask the corpus registry for the actor's authorized active chunks, with the
   snapshot filter applied inside the registry;
3. only then build a BM25 index from those returned chunks;
4. rank, select, and validate conflict pairs against the selection;
5. fetch stale candidates on a separate path that never feeds the index.

The retriever never reads SQL, never enumerates unauthorized chunk IDs, and
never accepts a client-provided candidate list.
"""

from __future__ import annotations

from datetime import date, datetime

from hallx.canonical import canonicalize
from hallx.corpus import CorpusRegistry
from hallx.models import (
    ConflictPair,
    EvidenceBundle,
    EvidenceChunk,
    Principal,
)
from hallx.retrieval.bundle import INDEX_VERSION, bundle_id_for, query_sha256, trace_id_for
from hallx.retrieval.errors import RetrievalError, RetrievalErrorCode
from hallx.retrieval.models import RetrievalResult, RetrievalTrace
from hallx.retrieval.sparse import SparseIndex, tokenize, validate_top_k


def _canonical_query(query: object) -> str:
    if not isinstance(query, str):
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_QUERY_INVALID,
            "query must be a string",
        )
    canonical = canonicalize(query).text
    if not canonical.strip() or not tokenize(canonical):
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_QUERY_INVALID,
            "query must contain at least one searchable token",
        )
    return canonical


def _require_snapshot_id(snapshot_id: object) -> str:
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_SNAPSHOT_INVALID,
            "snapshot_id is required and must not be blank",
        )
    return snapshot_id


def _require_as_of(as_of: object) -> date:
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_AS_OF_INVALID,
            "as_of must be a date",
        )
    return as_of


def _require_conflict_pairs(conflict_pairs: object) -> tuple[ConflictPair, ...]:
    try:
        pairs = tuple(conflict_pairs)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RetrievalError(
            RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID,
            "conflict_pairs must be iterable",
        ) from exc
    for pair in pairs:
        if not isinstance(pair, ConflictPair):
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID,
                "conflict_pairs must contain ConflictPair values",
            )
    return pairs


def _require_tenant(chunks: tuple[EvidenceChunk, ...], tenant_id: str) -> None:
    for chunk in chunks:
        if not isinstance(chunk, EvidenceChunk):
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_INDEX_INVALID,
                "registry returned a non-evidence chunk",
            )
        if chunk.tenant_id != tenant_id:
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_TENANT_MISMATCH,
                "evidence chunk tenant does not match the actor tenant",
            )


def _require_selected_conflicts(
    pairs: tuple[ConflictPair, ...], selected_ids: tuple[str, ...]
) -> None:
    selected = set(selected_ids)
    for pair in pairs:
        if pair.chunk_id_a not in selected or pair.chunk_id_b not in selected:
            raise RetrievalError(
                RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID,
                "a conflict pair references a chunk outside the selected set",
            )


class Retriever:
    """Sparse retrieval over P2-authorized active chunks only."""

    def __init__(self, registry: CorpusRegistry) -> None:
        self._registry = registry

    @property
    def index_version(self) -> str:
        return INDEX_VERSION

    def retrieve(
        self,
        actor: Principal,
        query: str,
        *,
        as_of: date,
        snapshot_id: str | None = None,
        top_k: int = 8,
        conflict_pairs: tuple[ConflictPair, ...] = (),
        include_stale: bool = True,
    ) -> RetrievalResult:
        frozen_snapshot = _require_snapshot_id(snapshot_id)
        canonical_query = _canonical_query(query)
        limit = validate_top_k(top_k)
        frozen_as_of = _require_as_of(as_of)
        pairs = _require_conflict_pairs(conflict_pairs)

        authorized = tuple(
            self._registry.authorized_chunks(
                actor,
                as_of=frozen_as_of,
                snapshot_id=frozen_snapshot,
            )
        )
        _require_tenant(authorized, actor.tenant_id)

        index = SparseIndex(authorized)
        scored = index.search(canonical_query, top_k=limit)
        by_id = {chunk.chunk_id: chunk for chunk in authorized}
        selected = tuple(by_id[score.chunk_id] for score in scored)
        selected_ids = tuple(chunk.chunk_id for chunk in selected)
        _require_selected_conflicts(pairs, selected_ids)

        stale_candidates: tuple[EvidenceChunk, ...] = ()
        if include_stale:
            stale_candidates = tuple(
                self._registry.stale_chunks(
                    actor,
                    as_of=frozen_as_of,
                    snapshot_id=frozen_snapshot,
                )
            )
            _require_tenant(stale_candidates, actor.tenant_id)
            stale_ids = {chunk.chunk_id for chunk in stale_candidates}
            if stale_ids.intersection(selected_ids):
                raise RetrievalError(
                    RetrievalErrorCode.RETRIEVAL_INDEX_INVALID,
                    "a chunk cannot be both active and stale",
                )

        query_digest = query_sha256(canonical_query)
        bundle_digest = bundle_id_for(frozen_snapshot, query_digest, selected_ids)
        bundle = EvidenceBundle(
            bundle_id=bundle_digest,
            snapshot_id=frozen_snapshot,
            tenant_id=actor.tenant_id,
            chunks=selected,
            conflict_pairs=pairs,
            stale_candidates=stale_candidates,
        )
        trace = RetrievalTrace(
            trace_id=trace_id_for(bundle_digest, INDEX_VERSION, limit),
            query_sha256=query_digest,
            snapshot_id=frozen_snapshot,
            as_of=frozen_as_of,
            index_version=INDEX_VERSION,
            candidate_count=len(authorized),
            selected_chunk_ids=selected_ids,
            stale_chunk_ids=tuple(chunk.chunk_id for chunk in stale_candidates),
            top_k=limit,
            scores=scored,
        )
        return RetrievalResult(bundle=bundle, trace=trace)


__all__ = ["Retriever"]
