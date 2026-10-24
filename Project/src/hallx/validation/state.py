"""Server-owned five-state evidence resolution and summary composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from hallx.models import (
    AbstentionAndConflictDiagnosis,
    ClaimSupportStatus,
    EvidenceBundle,
    EvidenceState,
    ValidatedClaim,
)
from hallx.validation.evidence import is_fresh


@dataclass(frozen=True, slots=True)
class StateResolution:
    state: EvidenceState
    conflict_ids: tuple[str, ...]
    stale_ids: tuple[str, ...]


def unresolved_conflict_ids(bundle: EvidenceBundle, as_of: date) -> tuple[str, ...]:
    chunks = {chunk.chunk_id: chunk for chunk in bundle.chunks}
    found: list[str] = []
    for pair in bundle.conflict_pairs:
        first = chunks.get(pair.chunk_id_a)
        second = chunks.get(pair.chunk_id_b)
        if first is None or second is None:
            continue
        if is_fresh(first, as_of) and is_fresh(second, as_of):
            found.extend((first.chunk_id, second.chunk_id))
    return tuple(dict.fromkeys(found))


def resolve_final_state(
    claims: tuple[ValidatedClaim, ...],
    bundle: EvidenceBundle,
    diagnosis: AbstentionAndConflictDiagnosis,
    *,
    as_of: date,
) -> StateResolution:
    """Derive the final state from validated facts only."""

    conflict_ids = unresolved_conflict_ids(bundle, as_of)
    stale_ids = tuple(
        chunk.chunk_id for chunk in bundle.stale_candidates if not is_fresh(chunk, as_of)
    )

    if conflict_ids:
        return StateResolution(EvidenceState.CONFLICTED, conflict_ids, stale_ids)
    if claims:
        if any(claim.support_status is ClaimSupportStatus.PARTIAL for claim in claims):
            return StateResolution(EvidenceState.PARTIAL, conflict_ids, stale_ids)
        if diagnosis.missing_information:
            return StateResolution(EvidenceState.PARTIAL, conflict_ids, stale_ids)
        return StateResolution(EvidenceState.SUPPORTED, conflict_ids, stale_ids)
    if stale_ids:
        return StateResolution(EvidenceState.STALE, conflict_ids, stale_ids)
    return StateResolution(EvidenceState.MISSING, conflict_ids, stale_ids)


def compose_diagnosis(
    original: AbstentionAndConflictDiagnosis,
    resolution: StateResolution,
    *,
    active_chunk_ids: tuple[str, ...],
) -> AbstentionAndConflictDiagnosis:
    """Replace model diagnostic references with server-verified ones."""

    allowed = set(active_chunk_ids)
    rejected = tuple(chunk_id for chunk_id in original.rejected_distractor_chunk_ids if chunk_id in allowed)
    missing = tuple(original.missing_information)
    if resolution.state is EvidenceState.PARTIAL and not missing:
        missing = ("The evidence supports only part of the requested information.",)
    if resolution.state is EvidenceState.MISSING and not missing:
        missing = ("No active, authorized evidence supports an answer.",)

    action = original.recommended_human_action.strip()
    if resolution.state is EvidenceState.SUPPORTED:
        action = action or "No action required."
    elif resolution.state is EvidenceState.CONFLICTED:
        action = action or "Review both conflicting sources before relying on an answer."
    elif resolution.state is EvidenceState.STALE:
        action = action or "Retrieve an active source before relying on an answer."
    elif resolution.state is EvidenceState.MISSING:
        action = action or "Provide or ingest an authoritative source."
    else:
        action = action or "Review the partial evidence before relying on an answer."

    return AbstentionAndConflictDiagnosis(
        missing_information=missing,
        rejected_distractor_chunk_ids=rejected,
        conflicting_chunk_ids=resolution.conflict_ids,
        stale_chunk_ids=resolution.stale_ids,
        recommended_human_action=action,
    )


def compose_summary(
    claims: tuple[ValidatedClaim, ...], resolution: StateResolution
) -> str:
    """Compose the displayed summary without unchecked model prose."""

    claim_text = " ".join(claim.claim_text.strip() for claim in claims).strip()
    if resolution.state is EvidenceState.SUPPORTED:
        return claim_text
    if resolution.state is EvidenceState.PARTIAL:
        if claim_text:
            return f"{claim_text} Some requested information is missing from the available evidence."
        return "The available evidence supports only part of the requested information."
    if resolution.state is EvidenceState.CONFLICTED:
        return "The active sources conflict. Human review is required before an answer is used."
    if resolution.state is EvidenceState.STALE:
        return "Only stale or superseded evidence is available. Human review is required."
    return "The available evidence does not answer this question."


def requires_human_review(state: EvidenceState) -> bool:
    return state is not EvidenceState.SUPPORTED
