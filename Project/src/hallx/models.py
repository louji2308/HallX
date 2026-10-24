"""Frozen data model for the HallX-Local evidence contract.

The model layer is deliberately strict:
- extra fields are forbidden;
- instances are frozen;
- content hashes are pattern-checked;
- chunk/evidence hashes are verified against canonical text on construction.

Authority still belongs to the validator: a well-formed model is not a
validated claim.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hallx.canonical import CANONICALIZATION_VERSION

SCHEMA_VERSION = "hallx-proof-envelope-v1"
_HEX64 = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class EvidenceState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"


class ClaimSupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"


class TriageStatus(str, Enum):
    RELEVANT_ACTIVE = "RELEVANT_ACTIVE"
    DISTRACTOR_IRRELEVANT = "DISTRACTOR_IRRELEVANT"
    SUPERSEDED_STALE = "SUPERSEDED_STALE"
    RESTRICTED_ACL = "RESTRICTED_ACL"
    ADVERSARIAL_IGNORED = "ADVERSARIAL_IGNORED"


class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    DRAFT = "DRAFT"


class Document(StrictModel):
    doc_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    uploaded_by: str = Field(min_length=1)
    created_at: datetime
    source_sha256: str = Field(pattern=_HEX64)
    acl_roles: tuple[str, ...] = Field(min_length=1)
    authority: str = Field(min_length=1)


class DocumentVersion(StrictModel):
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    status: DocumentStatus
    effective_from: date
    effective_until: date | None = None
    supersedes_version_id: str | None = None
    precedence_rule_id: str | None = None
    content_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str = CANONICALIZATION_VERSION

    @model_validator(mode="after")
    def _effective_window(self) -> "DocumentVersion":
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValueError("effective_until must not precede effective_from")
        return self


class Chunk(StrictModel):
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    original_text: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    canonical_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str = CANONICALIZATION_VERSION
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    acl_roles: tuple[str, ...] = Field(min_length=1)
    authority: str = Field(min_length=1)
    is_adversarial: bool = False

    @model_validator(mode="after")
    def _hash_and_pages(self) -> "Chunk":
        actual = hashlib.sha256(self.canonical_text.encode("utf-8")).hexdigest()
        if actual != self.canonical_sha256:
            raise ValueError("canonical_sha256 does not match canonical_text")
        if self.page_start is not None and self.page_end is not None:
            if self.page_end < self.page_start:
                raise ValueError("page_end must not precede page_start")
        return self


class CorpusSnapshot(StrictModel):
    snapshot_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=_HEX64)
    document_hashes: dict[str, str]
    version_hashes: dict[str, str]
    chunk_hashes: dict[str, str]
    split_membership: dict[str, tuple[str, ...]]
    split_lock_sha256: str = Field(pattern=_HEX64)
    index_version: str = Field(min_length=1)
    created_at: datetime


class Principal(StrictModel):
    principal_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    roles: tuple[str, ...] = Field(min_length=1)


class EvidenceChunk(StrictModel):
    """A frozen runtime view of one chunk and its provenance."""

    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    status: DocumentStatus
    effective_from: date
    effective_until: date | None = None
    authority: str = Field(min_length=1)
    acl_roles: tuple[str, ...] = Field(min_length=1)
    original_text: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    canonical_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str = CANONICALIZATION_VERSION
    source_sha256: str = Field(pattern=_HEX64)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    precedence_rule_id: str | None = None
    is_adversarial: bool = False

    @model_validator(mode="after")
    def _hash_and_pages(self) -> "EvidenceChunk":
        actual = hashlib.sha256(self.canonical_text.encode("utf-8")).hexdigest()
        if actual != self.canonical_sha256:
            raise ValueError("canonical_sha256 does not match canonical_text")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValueError("effective_until must not precede effective_from")
        if self.page_start is not None and self.page_end is not None:
            if self.page_end < self.page_start:
                raise ValueError("page_end must not precede page_start")
        return self


class ConflictPair(StrictModel):
    chunk_id_a: str = Field(min_length=1)
    chunk_id_b: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    precedence_rule_id: str | None = None

    @model_validator(mode="after")
    def _distinct(self) -> "ConflictPair":
        if self.chunk_id_a == self.chunk_id_b:
            raise ValueError("a conflict pair requires two distinct chunks")
        return self


class EvidenceBundle(StrictModel):
    bundle_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    chunks: tuple[EvidenceChunk, ...]
    conflict_pairs: tuple[ConflictPair, ...] = ()
    stale_candidates: tuple[EvidenceChunk, ...] = ()

    @model_validator(mode="after")
    def _unique_ids(self) -> "EvidenceBundle":
        ids = [chunk.chunk_id for chunk in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunks must have unique chunk_id values")
        stale_ids = [chunk.chunk_id for chunk in self.stale_candidates]
        if len(stale_ids) != len(set(stale_ids)):
            raise ValueError("stale_candidates must have unique chunk_id values")
        chunk_ids = set(ids)
        for pair in self.conflict_pairs:
            if pair.chunk_id_a not in chunk_ids or pair.chunk_id_b not in chunk_ids:
                raise ValueError("conflict pair references a chunk outside the bundle")
        return self


class GenerationChunkTriage(StrictModel):
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    triage_status: TriageStatus
    triage_reason: str


class GenerationClaim(StrictModel):
    claim_text: str = Field(min_length=1)
    support_status: ClaimSupportStatus
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    exact_quote: str = Field(min_length=1)
    numeric_values: tuple[str, ...] = ()
    claim_to_quote_rationale: str


class AbstentionAndConflictDiagnosis(StrictModel):
    missing_information: tuple[str, ...] = ()
    rejected_distractor_chunk_ids: tuple[str, ...] = ()
    conflicting_chunk_ids: tuple[str, ...] = ()
    stale_chunk_ids: tuple[str, ...] = ()
    recommended_human_action: str


class GenerationProofEnvelope(StrictModel):
    chunk_triage: tuple[GenerationChunkTriage, ...]
    evidence_state: EvidenceState
    answer_summary: str
    claims: tuple[GenerationClaim, ...]
    abstention_and_conflict_diagnosis: AbstentionAndConflictDiagnosis
    human_review_required: bool


class EntailmentResult(StrictModel):
    entailed: bool
    verifier_id: str = Field(min_length=1)
    score: float | None = None


class ValidatedClaim(GenerationClaim):
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    original_char_start: int = Field(ge=0)
    original_char_end: int = Field(ge=0)
    canonical_sha256: str = Field(pattern=_HEX64)
    source_sha256: str = Field(pattern=_HEX64)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    entailment_verifier_id: str = Field(min_length=1)
    entailment_score: float | None = None

    @model_validator(mode="after")
    def _span_order(self) -> "ValidatedClaim":
        if self.char_end <= self.char_start:
            raise ValueError("char_end must exceed char_start")
        if self.original_char_end <= self.original_char_start:
            raise ValueError("original_char_end must exceed original_char_start")
        return self


class ValidationResult(StrictModel):
    accepted: bool
    final_state: EvidenceState | None = None
    model_state: EvidenceState
    model_state_matches: bool
    issues: tuple["ValidationIssue", ...] = ()
    repair_allowed: bool = False
    final_human_review_required: bool = False
    canonicalization_version: str = CANONICALIZATION_VERSION
    schema_version: str = SCHEMA_VERSION


class ValidatedProofEnvelope(StrictModel):
    chunk_triage: tuple[GenerationChunkTriage, ...]
    evidence_state: EvidenceState
    answer_summary: str
    claims: tuple[ValidatedClaim, ...]
    abstention_and_conflict_diagnosis: AbstentionAndConflictDiagnosis
    human_review_required: bool
    validation_result: ValidationResult


class ValidationOutcome(StrictModel):
    accepted: bool
    envelope: ValidatedProofEnvelope | None = None
    result: ValidationResult

    @model_validator(mode="after")
    def _consistent(self) -> "ValidationOutcome":
        if self.accepted and self.envelope is None:
            raise ValueError("an accepted outcome requires an envelope")
        if not self.accepted and self.envelope is not None:
            raise ValueError("a rejected outcome must not expose an envelope")
        if self.result.accepted != self.accepted:
            raise ValueError("outcome and result acceptance must agree")
        return self


# Imported late to avoid a module cycle at import time.
from hallx.errors import ValidationIssue  # noqa: E402

ValidationResult.model_rebuild()
