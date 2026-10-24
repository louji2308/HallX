"""Shared fixtures and builders for Phase 1 unit tests."""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from hallx.canonical import canonicalize
from hallx.models import (
    AbstentionAndConflictDiagnosis,
    ClaimSupportStatus,
    ConflictPair,
    DocumentStatus,
    EntailmentResult,
    EvidenceBundle,
    EvidenceChunk,
    EvidenceState,
    GenerationChunkTriage,
    GenerationClaim,
    GenerationProofEnvelope,
    Principal,
    TriageStatus,
)

AS_OF = date(2026, 10, 24)
SOURCE_SHA = hashlib.sha256(b"source-document").hexdigest()


def make_evidence_chunk(
    chunk_id: str = "chunk-1",
    *,
    text: str = "The retention period is 30 days.",
    doc_id: str = "doc-1",
    version_id: str = "version-1",
    version_label: str = "v1",
    tenant_id: str = "tenant-a",
    status: DocumentStatus = DocumentStatus.ACTIVE,
    acl_roles: tuple[str, ...] = ("analyst",),
    authority: str = "policy",
    is_adversarial: bool = False,
    effective_from: date = date(2026, 1, 1),
    effective_until: date | None = None,
    page_start: int | None = 1,
    page_end: int | None = 1,
    precedence_rule_id: str | None = None,
    source_sha256: str = SOURCE_SHA,
) -> EvidenceChunk:
    canonical = canonicalize(text)
    return EvidenceChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        version_id=version_id,
        version_label=version_label,
        tenant_id=tenant_id,
        status=status,
        effective_from=effective_from,
        effective_until=effective_until,
        authority=authority,
        acl_roles=acl_roles,
        original_text=text,
        canonical_text=canonical.text,
        canonical_sha256=canonical.sha256,
        source_sha256=source_sha256,
        page_start=page_start,
        page_end=page_end,
        precedence_rule_id=precedence_rule_id,
        is_adversarial=is_adversarial,
    )


def make_principal(
    *, principal_id: str = "reviewer-1", tenant_id: str = "tenant-a", roles: tuple[str, ...] = ("analyst",)
) -> Principal:
    return Principal(principal_id=principal_id, tenant_id=tenant_id, roles=roles)


def make_bundle(
    chunks: tuple[EvidenceChunk, ...] = (),
    *,
    stale_candidates: tuple[EvidenceChunk, ...] = (),
    conflict_pairs: tuple[ConflictPair, ...] = (),
    bundle_id: str = "bundle-1",
    snapshot_id: str = "snapshot-1",
    tenant_id: str = "tenant-a",
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        chunks=chunks,
        conflict_pairs=conflict_pairs,
        stale_candidates=stale_candidates,
    )


def make_triage(
    chunk: EvidenceChunk, *, status: TriageStatus = TriageStatus.RELEVANT_ACTIVE, reason: str = "Directly relevant."
) -> GenerationChunkTriage:
    return GenerationChunkTriage(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        version=chunk.version_label,
        triage_status=status,
        triage_reason=reason,
    )


def make_claim(
    chunk: EvidenceChunk,
    *,
    claim_text: str | None = None,
    exact_quote: str | None = None,
    support_status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    numeric_values: tuple[str, ...] = (),
    doc_id: str | None = None,
    version: str | None = None,
) -> GenerationClaim:
    return GenerationClaim(
        claim_text=claim_text if claim_text is not None else chunk.canonical_text,
        support_status=support_status,
        chunk_id=chunk.chunk_id,
        doc_id=doc_id if doc_id is not None else chunk.doc_id,
        version=version if version is not None else chunk.version_label,
        exact_quote=exact_quote if exact_quote is not None else chunk.canonical_text,
        numeric_values=numeric_values,
        claim_to_quote_rationale="The quote states the claim directly.",
    )


def make_diagnosis(
    *,
    missing_information: tuple[str, ...] = (),
    rejected_distractor_chunk_ids: tuple[str, ...] = (),
    conflicting_chunk_ids: tuple[str, ...] = (),
    stale_chunk_ids: tuple[str, ...] = (),
    recommended_human_action: str = "Review the evidence before relying on an answer.",
) -> AbstentionAndConflictDiagnosis:
    return AbstentionAndConflictDiagnosis(
        missing_information=missing_information,
        rejected_distractor_chunk_ids=rejected_distractor_chunk_ids,
        conflicting_chunk_ids=conflicting_chunk_ids,
        stale_chunk_ids=stale_chunk_ids,
        recommended_human_action=recommended_human_action,
    )


def make_candidate(
    *,
    claims: tuple[GenerationClaim, ...] = (),
    triage: tuple[GenerationChunkTriage, ...] = (),
    state: EvidenceState = EvidenceState.SUPPORTED,
    answer_summary: str = "",
    diagnosis: AbstentionAndConflictDiagnosis | None = None,
    human_review_required: bool = False,
) -> GenerationProofEnvelope:
    return GenerationProofEnvelope(
        chunk_triage=triage,
        evidence_state=state,
        answer_summary=answer_summary,
        claims=claims,
        abstention_and_conflict_diagnosis=diagnosis if diagnosis is not None else make_diagnosis(),
        human_review_required=human_review_required,
    )


class StaticEntailmentVerifier:
    verifier_id = "test-entailment-v1"

    def __init__(self, *, entailed: bool = True) -> None:
        self.entailed = entailed
        self.calls: list[tuple[str, str, str]] = []

    def check(self, *, claim_text: str, exact_quote: str, chunk: EvidenceChunk) -> EntailmentResult:
        self.calls.append((claim_text, exact_quote, chunk.chunk_id))
        return EntailmentResult(
            entailed=self.entailed,
            verifier_id=self.verifier_id,
            score=0.99 if self.entailed else 0.0,
        )
