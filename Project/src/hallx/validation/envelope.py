"""Envelope validation: the server truth boundary for Phase 1."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Protocol, Sequence

from pydantic import ValidationError

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize
from hallx.errors import (
    ErrorCode,
    REPAIRABLE_CODES,
    Severity,
    SourceMapError,
    SpanResolutionError,
    ValidationIssue,
    issue,
)
from hallx.models import (
    EntailmentResult,
    EvidenceBundle,
    EvidenceChunk,
    EvidenceState,
    GenerationChunkTriage,
    GenerationClaim,
    GenerationProofEnvelope,
    Principal,
    TriageStatus,
    ValidatedClaim,
    ValidatedProofEnvelope,
    ValidationOutcome,
    ValidationResult,
)
from hallx.validation.evidence import is_fresh, validate_evidence_bundle
from hallx.validation.numeric import check_numeric_consistency
from hallx.validation.span import resolve_unique_quote
from hallx.validation.state import (
    compose_diagnosis,
    compose_summary,
    requires_human_review,
    resolve_final_state,
)


class EntailmentVerifier(Protocol):
    verifier_id: str

    def check(
        self, *, claim_text: str, exact_quote: str, chunk: EvidenceChunk
    ) -> EntailmentResult: ...


def validate_envelope(
    candidate: GenerationProofEnvelope | Mapping[str, Any],
    bundle: EvidenceBundle,
    principal: Principal,
    *,
    as_of: date,
    previous_repairs: int = 0,
    entailment: EntailmentVerifier | None = None,
) -> ValidationOutcome:
    """Validate a model candidate against frozen evidence.

    This function is deterministic. It never mutates the candidate, never
    trusts model offsets/state/ACL/freshness, and fails closed when the
    entailment verifier is absent.
    """

    parsed, schema_issue = _coerce_candidate(candidate)
    if schema_issue is not None:
        return _reject(
            model_state=EvidenceState.MISSING,
            issues=(schema_issue,),
            previous_repairs=previous_repairs,
        )
    assert parsed is not None

    bundle_issues = validate_evidence_bundle(bundle, principal)
    issues: list[ValidationIssue] = list(bundle_issues)
    chunks = {chunk.chunk_id: chunk for chunk in bundle.chunks}
    stale_chunks = {chunk.chunk_id: chunk for chunk in bundle.stale_candidates}

    validated_claims: list[ValidatedClaim] = []
    if not any(item.blocking for item in bundle_issues):
        issues.extend(_check_triage(parsed.chunk_triage, chunks))
        triage_by_id = {entry.chunk_id: entry for entry in parsed.chunk_triage}
        for index, claim in enumerate(parsed.claims):
            claim_issues, validated = _validate_claim(
                claim,
                index=index,
                chunks=chunks,
                stale_chunks=stale_chunks,
                triage_by_id=triage_by_id,
                as_of=as_of,
                entailment=entailment,
            )
            issues.extend(claim_issues)
            if validated is not None:
                validated_claims.append(validated)

    issues = _dedupe(issues)
    if any(item.blocking for item in issues):
        return _reject(
            model_state=parsed.evidence_state,
            issues=tuple(issues),
            previous_repairs=previous_repairs,
        )

    resolution = resolve_final_state(
        tuple(validated_claims), bundle, parsed.abstention_and_conflict_diagnosis, as_of=as_of
    )
    final_diagnosis = compose_diagnosis(
        parsed.abstention_and_conflict_diagnosis,
        resolution,
        active_chunk_ids=tuple(chunks),
    )
    summary = compose_summary(tuple(validated_claims), resolution)
    if parsed.evidence_state is not resolution.state:
        issues.append(
            issue(
                ErrorCode.EVIDENCE_STATE_MISMATCH,
                "server state differs from the model candidate state",
                severity=Severity.WARNING,
            )
        )

    result = ValidationResult(
        accepted=True,
        final_state=resolution.state,
        model_state=parsed.evidence_state,
        model_state_matches=parsed.evidence_state is resolution.state,
        issues=tuple(issues),
        repair_allowed=False,
        final_human_review_required=requires_human_review(resolution.state),
    )
    envelope = ValidatedProofEnvelope(
        chunk_triage=parsed.chunk_triage,
        evidence_state=resolution.state,
        answer_summary=summary,
        claims=tuple(validated_claims),
        abstention_and_conflict_diagnosis=final_diagnosis,
        human_review_required=requires_human_review(resolution.state),
        validation_result=result,
    )
    return ValidationOutcome(accepted=True, envelope=envelope, result=result)


def _coerce_candidate(
    candidate: GenerationProofEnvelope | Mapping[str, Any],
) -> tuple[GenerationProofEnvelope | None, ValidationIssue | None]:
    if isinstance(candidate, GenerationProofEnvelope):
        return candidate, None
    if not isinstance(candidate, Mapping):
        return None, issue(
            ErrorCode.SCHEMA_INVALID,
            "candidate must be a GenerationProofEnvelope or a mapping",
        )
    try:
        return GenerationProofEnvelope.model_validate(dict(candidate)), None
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors(include_url=False, include_input=False)
        )
        return None, issue(
            ErrorCode.SCHEMA_INVALID,
            f"candidate does not match the generation schema: {details[:500]}",
        )


def _check_triage(
    triage: Sequence[GenerationChunkTriage],
    chunks: Mapping[str, EvidenceChunk],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for entry in triage:
        if entry.chunk_id in seen:
            issues.append(
                issue(
                    ErrorCode.TRIAGE_DUPLICATE,
                    "chunk triage contains a duplicate chunk id",
                    chunk_id=entry.chunk_id,
                )
            )
            continue
        seen.add(entry.chunk_id)
        chunk = chunks.get(entry.chunk_id)
        if chunk is None:
            issues.append(
                issue(
                    ErrorCode.TRIAGE_UNKNOWN_CHUNK,
                    "chunk triage references a chunk outside the active bundle",
                    chunk_id=entry.chunk_id,
                )
            )
            continue
        if entry.doc_id != chunk.doc_id or entry.version != chunk.version_label:
            issues.append(
                issue(
                    ErrorCode.TRIAGE_IDENTITY_MISMATCH,
                    "chunk triage identity does not match the bundle",
                    chunk_id=entry.chunk_id,
                )
            )
    missing = set(chunks).difference(seen)
    if missing:
        issues.append(
            issue(
                ErrorCode.TRIAGE_INCOMPLETE,
                f"chunk triage is missing {len(missing)} active chunk(s)",
            )
        )
    return issues


def _validate_claim(
    claim: GenerationClaim,
    *,
    index: int,
    chunks: Mapping[str, EvidenceChunk],
    stale_chunks: Mapping[str, EvidenceChunk],
    triage_by_id: Mapping[str, GenerationChunkTriage],
    as_of: date,
    entailment: EntailmentVerifier | None,
) -> tuple[list[ValidationIssue], ValidatedClaim | None]:
    issues: list[ValidationIssue] = []

    chunk = chunks.get(claim.chunk_id)
    if chunk is None:
        code = ErrorCode.SOURCE_STALE if claim.chunk_id in stale_chunks else ErrorCode.UNKNOWN_CHUNK
        issues.append(
            issue(
                code,
                "claim cites a chunk that is not an active authorized source",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    if claim.doc_id != chunk.doc_id or claim.version != chunk.version_label:
        issues.append(
            issue(
                ErrorCode.SOURCE_IDENTITY_MISMATCH,
                "claim source identity does not match the bundle",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
    triage = triage_by_id.get(claim.chunk_id)
    if triage is not None and triage.triage_status is not TriageStatus.RELEVANT_ACTIVE:
        issues.append(
            issue(
                ErrorCode.CLAIM_TRIAGE_MISMATCH,
                "claim cites a chunk the candidate itself marked as non-relevant",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )

    if not is_fresh(chunk, as_of):
        code = (
            ErrorCode.SOURCE_EXPIRED
            if chunk.effective_until is not None and chunk.effective_until < as_of
            else ErrorCode.SOURCE_STALE
        )
        issues.append(
            issue(
                code,
                "claim source is not active and fresh at the evaluation date",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )

    if chunk.is_adversarial:
        issues.append(
            issue(
                ErrorCode.ADVERSARIAL_EVIDENCE,
                "claim cites evidence marked as adversarial",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    if chunk.canonicalization_version != CANONICALIZATION_VERSION:
        issues.append(
            issue(
                ErrorCode.CANONICALIZATION_MISMATCH,
                "claim cites a chunk with an unsupported canonicalization version",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    regenerated = canonicalize(chunk.original_text)
    if regenerated.text != chunk.canonical_text or regenerated.sha256 != chunk.canonical_sha256:
        issues.append(
            issue(
                ErrorCode.CANONICALIZATION_MISMATCH,
                "claim chunk canonical text does not reproduce from its source",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    try:
        char_start, char_end = resolve_unique_quote(chunk.canonical_text, claim.exact_quote)
    except SpanResolutionError as exc:
        issues.append(
            issue(
                exc.code,
                str(exc),
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    try:
        original_start, original_end = regenerated.to_original_span(char_start, char_end)
    except SourceMapError as exc:
        issues.append(
            issue(
                ErrorCode.SOURCE_MAP_UNSUPPORTED,
                str(exc),
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return issues, None

    for mismatch in check_numeric_consistency(
        claim.claim_text, claim.exact_quote, claim.numeric_values
    ):
        issues.append(
            issue(
                ErrorCode.NUMERIC_MISMATCH,
                f"numeric consistency failed: {mismatch.kind}",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )

    entailed, entailment_id, entailment_score = _check_entailment(
        claim, chunk, entailment, index=index, issues=issues
    )
    if not entailed:
        return issues, None
    if any(item.blocking for item in issues):
        return issues, None

    return issues, ValidatedClaim(
        claim_text=claim.claim_text,
        support_status=claim.support_status,
        chunk_id=claim.chunk_id,
        doc_id=claim.doc_id,
        version=claim.version,
        exact_quote=claim.exact_quote,
        numeric_values=claim.numeric_values,
        claim_to_quote_rationale=claim.claim_to_quote_rationale,
        char_start=char_start,
        char_end=char_end,
        original_char_start=original_start,
        original_char_end=original_end,
        canonical_sha256=chunk.canonical_sha256,
        source_sha256=chunk.source_sha256,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        entailment_verifier_id=entailment_id,
        entailment_score=entailment_score,
    )


def _check_entailment(
    claim: GenerationClaim,
    chunk: EvidenceChunk,
    entailment: EntailmentVerifier | None,
    *,
    index: int,
    issues: list[ValidationIssue],
) -> tuple[bool, str, float | None]:
    if entailment is None:
        issues.append(
            issue(
                ErrorCode.CITATION_NOT_ENTAILED,
                "no independent entailment verifier is configured; citation support is unproven",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return False, "unconfigured", None

    try:
        result = entailment.check(
            claim_text=claim.claim_text,
            exact_quote=claim.exact_quote,
            chunk=chunk,
        )
    except Exception:
        issues.append(
            issue(
                ErrorCode.INTERNAL_ERROR,
                "entailment verifier failed; citation support is unproven",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return False, "error", None

    if not isinstance(result, EntailmentResult):
        issues.append(
            issue(
                ErrorCode.INTERNAL_ERROR,
                "entailment verifier returned an invalid result",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return False, "invalid", None
    if result.verifier_id != entailment.verifier_id:
        issues.append(
            issue(
                ErrorCode.INTERNAL_ERROR,
                "entailment verifier identity does not match its result",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return False, result.verifier_id, result.score
    if not result.entailed:
        issues.append(
            issue(
                ErrorCode.CITATION_NOT_ENTAILED,
                "the exact quote does not entail the claim",
                chunk_id=claim.chunk_id,
                claim_index=index,
            )
        )
        return False, result.verifier_id, result.score
    return True, result.verifier_id, result.score


def _dedupe(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    unique: dict[tuple[object, ...], ValidationIssue] = {}
    for item in issues:
        key = (
            item.code,
            item.severity,
            item.chunk_id,
            item.claim_index,
            item.message,
        )
        unique[key] = item
    return list(unique.values())


def _reject(
    *,
    model_state: EvidenceState,
    issues: Sequence[ValidationIssue],
    previous_repairs: int,
) -> ValidationOutcome:
    blocking = [item for item in issues if item.blocking]
    repair_allowed = (
        previous_repairs < 1
        and bool(blocking)
        and all(item.code in REPAIRABLE_CODES for item in blocking)
    )
    result = ValidationResult(
        accepted=False,
        final_state=None,
        model_state=model_state,
        model_state_matches=False,
        issues=tuple(issues),
        repair_allowed=repair_allowed,
        final_human_review_required=True,
    )
    return ValidationOutcome(accepted=False, envelope=None, result=result)
