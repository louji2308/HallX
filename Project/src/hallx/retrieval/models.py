"""Frozen P3B retrieval models.

The models encode the retrieval contract, not just its shape: an active
bundle entry must be currently effective, a stale candidate must be
superseded or expired, the trace must describe exactly the bundle it was
produced with, and scores must follow the selected order. These checks fail
closed so an inconsistent bundle can never be handed to a model.
"""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hallx.models import DocumentStatus, EvidenceBundle

_HEX64 = r"^[0-9a-f]{64}$"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class ScoredChunk(_FrozenModel):
    chunk_id: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=0)

    @model_validator(mode="after")
    def _finite_score(self) -> ScoredChunk:
        if not math.isfinite(self.score):
            raise ValueError("score must be finite")
        return self


class RetrievalTrace(_FrozenModel):
    trace_id: str = Field(min_length=1)
    query_sha256: str = Field(pattern=_HEX64)
    snapshot_id: str = Field(min_length=1)
    as_of: date
    index_version: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    selected_chunk_ids: tuple[str, ...]
    stale_chunk_ids: tuple[str, ...]
    top_k: int = Field(gt=0)
    scores: tuple[ScoredChunk, ...]

    @model_validator(mode="after")
    def _consistent(self) -> RetrievalTrace:
        selected = self.selected_chunk_ids
        stale = self.stale_chunk_ids
        if len(selected) != len(set(selected)):
            raise ValueError("selected_chunk_ids must be unique")
        if len(stale) != len(set(stale)):
            raise ValueError("stale_chunk_ids must be unique")
        if set(selected).intersection(stale):
            raise ValueError("a chunk cannot be both active and stale")
        if len(selected) > self.top_k:
            raise ValueError("selection must not exceed top_k")
        if self.candidate_count < len(selected):
            raise ValueError("candidate_count must cover the selected chunks")
        if tuple(scored.chunk_id for scored in self.scores) != selected:
            raise ValueError("scores must follow the selected chunk order")
        if tuple(scored.rank for scored in self.scores) != tuple(range(len(self.scores))):
            raise ValueError("score ranks must be contiguous from zero")
        return self


class RetrievalResult(_FrozenModel):
    bundle: EvidenceBundle
    trace: RetrievalTrace

    @model_validator(mode="after")
    def _consistent(self) -> RetrievalResult:
        if self.bundle.snapshot_id != self.trace.snapshot_id:
            raise ValueError("bundle and trace snapshot ids must agree")
        active_ids = tuple(chunk.chunk_id for chunk in self.bundle.chunks)
        stale_ids = tuple(chunk.chunk_id for chunk in self.bundle.stale_candidates)
        if active_ids != self.trace.selected_chunk_ids:
            raise ValueError("trace selected ids must match the active bundle")
        if stale_ids != self.trace.stale_chunk_ids:
            raise ValueError("trace stale ids must match the stale candidates")

        for chunk in self.bundle.chunks:
            if chunk.status is not DocumentStatus.ACTIVE:
                raise ValueError("active bundle chunks must be active")
            if chunk.tenant_id != self.bundle.tenant_id:
                raise ValueError("active bundle chunks must match the bundle tenant")
            if chunk.effective_from > self.trace.as_of:
                raise ValueError("active bundle chunk is not yet effective")
            if chunk.effective_until is not None and chunk.effective_until < self.trace.as_of:
                raise ValueError("active bundle chunk has expired")

        for stale in self.bundle.stale_candidates:
            if stale.status not in (DocumentStatus.SUPERSEDED, DocumentStatus.EXPIRED):
                raise ValueError("stale candidates must be superseded or expired")
            if stale.tenant_id != self.bundle.tenant_id:
                raise ValueError("stale candidates must match the bundle tenant")
        return self


__all__ = ["RetrievalResult", "RetrievalTrace", "ScoredChunk"]
