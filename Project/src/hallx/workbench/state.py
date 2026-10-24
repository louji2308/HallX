"""Synthetic fixture state for the P5 reviewer workbench shell.

Every record in this module is invented for layout review. No retrieval,
generation, ACL decision, validation, or PDF mapping was executed to produce
it. The renderer must always present these records as fixtures and must never
promote them to verified evidence.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hallx.models import ClaimSupportStatus, EvidenceState, TriageStatus

FIXTURE_BANNER = "FIXTURE DATA — NOT A VERIFIED RUN"
FIXTURE_BADGE = "FIXTURE"
OFFSET_WARNING = "FIXTURE OFFSET — NOT A REAL HIGHLIGHT"
UNSUPPORTED_MAP_LABEL = "SOURCE MAP UNSUPPORTED"

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class MapStatus(str, Enum):
    MAPPED = "MAPPED"
    UNSUPPORTED = "UNSUPPORTED"


class VersionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ClaimFixture(BaseModel):
    model_config = _FROZEN

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    support_status: ClaimSupportStatus
    numeric_check: str = Field(min_length=1)
    entailment_check: str = Field(min_length=1)


class SourceFixture(BaseModel):
    model_config = _FROZEN

    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    doc_title: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    chunk_text: str = Field(min_length=1)
    map_status: MapStatus
    map_reason: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    page_label: str | None = None

    @model_validator(mode="after")
    def _mapping_is_explicit(self) -> SourceFixture:
        has_offsets = self.char_start is not None or self.char_end is not None
        if self.map_status is MapStatus.UNSUPPORTED and has_offsets:
            raise ValueError("unsupported source maps must not carry fixture offsets")
        if self.map_status is MapStatus.MAPPED:
            if self.char_start is None or self.char_end is None:
                raise ValueError("mapped sources require fixture offsets")
            if self.char_end <= self.char_start:
                raise ValueError("mapped fixture offsets must be ordered")
        return self


class TraceEventFixture(BaseModel):
    model_config = _FROZEN

    event_id: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    recorded_at: str = Field(min_length=1)


class RunChunkFixture(BaseModel):
    model_config = _FROZEN

    chunk_id: str = Field(min_length=1)
    triage: TriageStatus
    reason: str = Field(min_length=1)


class RunFixture(BaseModel):
    model_config = _FROZEN

    run_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    state: EvidenceState
    status: RunStatus
    created_at: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    diagnostic: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    repair_attempts: int = Field(ge=0, le=1)
    claims: tuple[ClaimFixture, ...] = ()
    chunks: tuple[RunChunkFixture, ...] = ()
    trace: tuple[TraceEventFixture, ...] = ()
    escalation_id: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _state_and_status_are_consistent(self) -> RunFixture:
        if self.status is RunStatus.FAILED and not self.error:
            raise ValueError("failed runs require an explicit safe-abstention error")
        if self.status is RunStatus.COMPLETE and self.error:
            raise ValueError("completed runs must not carry a failure error")
        if self.state is EvidenceState.SUPPORTED and not self.claims:
            raise ValueError("supported runs require validated claim fixtures")
        if self.state in (
            EvidenceState.MISSING,
            EvidenceState.CONFLICTED,
            EvidenceState.STALE,
        ) and self.claims:
            raise ValueError(f"{self.state.value} runs must not display factual claims")
        return self


class DocumentVersionFixture(BaseModel):
    model_config = _FROZEN

    version_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: VersionStatus
    effective_from: str = Field(min_length=1)
    effective_to: str | None = None
    supersedes: str | None = None
    acl_roles: tuple[str, ...] = ()
    digest_label: str = Field(min_length=1)
    chunk_ids: tuple[str, ...] = ()


class DocumentFixture(BaseModel):
    model_config = _FROZEN

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    versions: tuple[DocumentVersionFixture, ...] = Field(min_length=1)


class EscalationEventFixture(BaseModel):
    model_config = _FROZEN

    event_id: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    action: str = Field(min_length=1)
    from_status: str = Field(min_length=1)
    to_status: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class EscalationFixture(BaseModel):
    model_config = _FROZEN

    case_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    opened_at: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    audit_events: tuple[EscalationEventFixture, ...] = Field(min_length=1)


class AdjudicateFixture(BaseModel):
    model_config = _FROZEN

    run_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)


class WorkbenchState(BaseModel):
    model_config = _FROZEN

    fixture_banner: str = FIXTURE_BANNER
    fixture_badge: str = FIXTURE_BADGE
    offset_warning: str = OFFSET_WARNING
    unsupported_label: str = UNSUPPORTED_MAP_LABEL
    adjudicate: AdjudicateFixture
    runs: tuple[RunFixture, ...] = Field(min_length=1)
    documents: tuple[DocumentFixture, ...] = Field(min_length=1)
    escalations: tuple[EscalationFixture, ...] = ()
    sources: tuple[SourceFixture, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _references_are_resolvable(self) -> WorkbenchState:
        run_ids = [run.run_id for run in self.runs]
        doc_ids = [doc.doc_id for doc in self.documents]
        source_ids = [source.chunk_id for source in self.sources]
        case_ids = [case.case_id for case in self.escalations]
        if len(set(run_ids)) != len(run_ids):
            raise ValueError("duplicate fixture run ids")
        if len(set(doc_ids)) != len(doc_ids):
            raise ValueError("duplicate fixture document ids")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("duplicate fixture source ids")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("duplicate fixture escalation ids")
        if self.adjudicate.run_id not in run_ids:
            raise ValueError("adjudicate fixture must reference an existing run")

        sources = {source.chunk_id: source for source in self.sources}
        runs = {run.run_id: run for run in self.runs}
        for run in self.runs:
            for chunk in run.chunks:
                if chunk.chunk_id not in sources:
                    raise ValueError(f"{run.run_id} references unknown chunk {chunk.chunk_id}")
            for claim in run.claims:
                source = sources.get(claim.chunk_id)
                if source is None:
                    raise ValueError(f"{run.run_id} cites unknown chunk {claim.chunk_id}")
                if claim.quote not in source.chunk_text:
                    raise ValueError(f"claim {claim.claim_id} quote is absent from its source")
            if run.escalation_id is not None and run.escalation_id not in case_ids:
                raise ValueError(f"{run.run_id} references unknown escalation")
        for doc in self.documents:
            if not any(version.status is VersionStatus.ACTIVE for version in doc.versions):
                raise ValueError(f"{doc.doc_id} has no active fixture version")
            for version in doc.versions:
                for chunk_id in version.chunk_ids:
                    if chunk_id not in sources:
                        raise ValueError(f"{doc.doc_id} references unknown chunk {chunk_id}")
        for case in self.escalations:
            if case.run_id not in runs:
                raise ValueError(f"{case.case_id} references unknown run")
        return self


def _source(
    *,
    chunk_id: str,
    doc_id: str,
    doc_title: str,
    version_label: str,
    text: str,
    mapped: bool,
    reason: str,
    page_label: str | None = None,
) -> SourceFixture:
    if mapped:
        return SourceFixture(
            chunk_id=chunk_id,
            doc_id=doc_id,
            doc_title=doc_title,
            version_label=version_label,
            chunk_text=text,
            map_status=MapStatus.MAPPED,
            map_reason=reason,
            char_start=0,
            char_end=len(text),
            page_label=page_label,
        )
    return SourceFixture(
        chunk_id=chunk_id,
        doc_id=doc_id,
        doc_title=doc_title,
        version_label=version_label,
        chunk_text=text,
        map_status=MapStatus.UNSUPPORTED,
        map_reason=reason,
        page_label=page_label,
    )


def build_fixture_state() -> WorkbenchState:
    """Build the frozen, fully synthetic demo state for the reviewer shell."""

    access_title = "Helios Remote Access Policy (synthetic fixture)"
    retention_global_title = "Helios Records Retention Standard (synthetic fixture)"
    retention_regional_title = "Helios Regional Retention Addendum (synthetic fixture)"

    mfa_text = (
        "Remote access to production systems requires multi-factor authentication. "
        "Contractor sessions expire after 15 minutes of inactivity."
    )
    review_text = "Privileged access reviews are performed quarterly by the platform owner."
    scanned_text = (
        "Contractor onboarding includes an access acknowledgement and a manager attestation."
    )
    legacy_text = "Remote access to production systems requires a password and a hardware token."
    seven_year_text = (
        "Customer records must be retained for seven years after account closure."
    )
    ten_year_text = "Customer records must be retained for ten years after account closure."

    sources = (
        _source(
            chunk_id="chunk-access-v2-mfa",
            doc_id="doc-helios-access",
            doc_title=access_title,
            version_label="v2.0",
            text=mfa_text,
            mapped=True,
            reason="Fixture text-item map exists for the synthetic access policy.",
            page_label="Fixture page 4",
        ),
        _source(
            chunk_id="chunk-access-v2-reviews",
            doc_id="doc-helios-access",
            doc_title=access_title,
            version_label="v2.0",
            text=review_text,
            mapped=True,
            reason="Fixture text-item map exists for the synthetic access policy.",
            page_label="Fixture page 5",
        ),
        _source(
            chunk_id="chunk-access-v2-scanned",
            doc_id="doc-helios-access",
            doc_title=access_title,
            version_label="v2.0",
            text=scanned_text,
            mapped=False,
            reason=(
                "The synthetic fixture source is marked as a scanned image and has no "
                "server-side text-item map."
            ),
            page_label="Fixture scan 1",
        ),
        _source(
            chunk_id="chunk-access-v1-legacy",
            doc_id="doc-helios-access",
            doc_title=access_title,
            version_label="v1.0",
            text=legacy_text,
            mapped=True,
            reason="Fixture text-item map exists for the superseded access policy.",
            page_label="Fixture page 2",
        ),
        _source(
            chunk_id="chunk-retention-seven",
            doc_id="doc-retention-global",
            doc_title=retention_global_title,
            version_label="v2.1",
            text=seven_year_text,
            mapped=True,
            reason="Fixture text-item map exists for the synthetic retention standard.",
            page_label="Fixture page 1",
        ),
        _source(
            chunk_id="chunk-retention-ten",
            doc_id="doc-retention-regional",
            doc_title=retention_regional_title,
            version_label="v1.4",
            text=ten_year_text,
            mapped=True,
            reason="Fixture text-item map exists for the synthetic regional addendum.",
            page_label="Fixture page 2",
        ),
    )

    claims = (
        ClaimFixture(
            claim_id="claim-fixture-mfa",
            text="Remote production access requires multi-factor authentication.",
            quote="Remote access to production systems requires multi-factor authentication.",
            chunk_id="chunk-access-v2-mfa",
            support_status=ClaimSupportStatus.SUPPORTED,
            numeric_check="FIXTURE PASS — no numeric value in this claim",
            entailment_check="FIXTURE RECORD — independent fixture entailment check not executed",
        ),
        ClaimFixture(
            claim_id="claim-fixture-expiry",
            text="Contractor sessions expire after 15 minutes of inactivity.",
            quote="Contractor sessions expire after 15 minutes of inactivity.",
            chunk_id="chunk-access-v2-mfa",
            support_status=ClaimSupportStatus.SUPPORTED,
            numeric_check="FIXTURE PASS — 15 minutes matches the synthetic source",
            entailment_check="FIXTURE RECORD — independent fixture entailment check not executed",
        ),
    )

    runs = (
        RunFixture(
            run_id="run-fixture-supported",
            question=(
                "How must remote production access be authenticated, and when do "
                "contractor sessions expire?"
            ),
            scope="Helios Remote Access Policy v2.0 (synthetic fixture)",
            state=EvidenceState.SUPPORTED,
            status=RunStatus.COMPLETE,
            created_at="2026-10-24T09:02:00Z",
            summary=(
                "Remote production access requires multi-factor authentication, and "
                "contractor sessions expire after 15 minutes of inactivity."
            ),
            diagnostic=(
                "Both fixture claims cite one active synthetic source. Offsets appear only "
                "inside the Source Inspector and are labeled fixture offsets."
            ),
            recommended_action="No reviewer action is required in this fixture preview.",
            repair_attempts=0,
            claims=claims,
            chunks=(
                RunChunkFixture(
                    chunk_id="chunk-access-v2-mfa",
                    triage=TriageStatus.RELEVANT_ACTIVE,
                    reason="Directly supports both fixture claims.",
                ),
                RunChunkFixture(
                    chunk_id="chunk-access-v1-legacy",
                    triage=TriageStatus.SUPERSEDED_STALE,
                    reason="Superseded fixture version; excluded from current support.",
                ),
            ),
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-supported-1",
                    stage="record",
                    outcome="FIXTURE SEEDED — no retrieval, generation, or validation executed",
                    recorded_at="2026-10-24T09:02:00Z",
                ),
            ),
        ),
        RunFixture(
            run_id="run-fixture-partial",
            question="Are quarterly access reviews required for contractors?",
            scope="Helios Remote Access Policy v2.0 (synthetic fixture)",
            state=EvidenceState.PARTIAL,
            status=RunStatus.COMPLETE,
            created_at="2026-10-24T09:05:00Z",
            summary=(
                "The fixture source establishes quarterly privileged access reviews but "
                "does not establish a contractor-specific review cadence."
            ),
            diagnostic=(
                "Missing premise: the fixture contains no contractor-specific review "
                "cadence. Only the validated portion is displayed."
            ),
            recommended_action="Route to the identity owner for the missing cadence.",
            repair_attempts=0,
            claims=(
                ClaimFixture(
                    claim_id="claim-fixture-reviews",
                    text="Privileged access reviews are performed quarterly.",
                    quote="Privileged access reviews are performed quarterly by the platform owner.",
                    chunk_id="chunk-access-v2-reviews",
                    support_status=ClaimSupportStatus.PARTIAL,
                    numeric_check="FIXTURE PASS — quarterly cadence matches the synthetic source",
                    entailment_check=(
                        "FIXTURE RECORD — independent fixture entailment check not executed"
                    ),
                ),
            ),
            chunks=(
                RunChunkFixture(
                    chunk_id="chunk-access-v2-reviews",
                    triage=TriageStatus.RELEVANT_ACTIVE,
                    reason="Supports the quarter cadence, not the contractor scope.",
                ),
            ),
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-partial-1",
                    stage="record",
                    outcome="FIXTURE SEEDED — missing premise recorded by hand",
                    recorded_at="2026-10-24T09:05:00Z",
                ),
            ),
        ),
        RunFixture(
            run_id="run-fixture-conflicted",
            question="How long must customer records be retained after account closure?",
            scope="Helios retention fixtures (two synthetic active scopes)",
            state=EvidenceState.CONFLICTED,
            status=RunStatus.COMPLETE,
            created_at="2026-10-24T09:10:00Z",
            summary=(
                "Two active synthetic sources disagree about the retention period. The "
                "reviewer shell does not synthesize a single answer."
            ),
            diagnostic=(
                "Both conflicting sources are active and authorized in the fixture. No "
                "precedence rule resolves the seven-year versus ten-year disagreement."
            ),
            recommended_action="Review both spans and route the case to a knowledge owner.",
            repair_attempts=0,
            chunks=(
                RunChunkFixture(
                    chunk_id="chunk-retention-seven",
                    triage=TriageStatus.RELEVANT_ACTIVE,
                    reason="Active synthetic source claiming a seven-year period.",
                ),
                RunChunkFixture(
                    chunk_id="chunk-retention-ten",
                    triage=TriageStatus.RELEVANT_ACTIVE,
                    reason="Active synthetic source claiming a ten-year period.",
                ),
            ),
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-conflicted-1",
                    stage="record",
                    outcome="FIXTURE SEEDED — unresolved conflict recorded by hand",
                    recorded_at="2026-10-24T09:10:00Z",
                ),
            ),
            escalation_id="case-fixture-conflict-001",
        ),
        RunFixture(
            run_id="run-fixture-stale",
            question="May remote access rely on a password plus a hardware token?",
            scope="Helios Remote Access Policy (synthetic fixture)",
            state=EvidenceState.STALE,
            status=RunStatus.COMPLETE,
            created_at="2026-10-24T09:12:00Z",
            summary=(
                "Only a superseded synthetic source matches the question. Stale text is "
                "not presented as current authority."
            ),
            diagnostic=(
                "The matching fixture version is superseded by v2.0. No active synthetic "
                "source supports the old token statement."
            ),
            recommended_action="Retrieve an active source before relying on an answer.",
            repair_attempts=0,
            chunks=(
                RunChunkFixture(
                    chunk_id="chunk-access-v1-legacy",
                    triage=TriageStatus.SUPERSEDED_STALE,
                    reason="Superseded fixture version; never used as current support.",
                ),
            ),
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-stale-1",
                    stage="record",
                    outcome="FIXTURE SEEDED — stale-only fixture path",
                    recorded_at="2026-10-24T09:12:00Z",
                ),
            ),
        ),
        RunFixture(
            run_id="run-fixture-missing",
            question="What is the executive travel reimbursement limit?",
            scope="Helios policy fixtures (synthetic corpus)",
            state=EvidenceState.MISSING,
            status=RunStatus.COMPLETE,
            created_at="2026-10-24T09:13:00Z",
            summary="No active synthetic fixture source addresses executive travel reimbursement.",
            diagnostic=(
                "The fixture evidence bundle is empty. No factual answer claims are shown."
            ),
            recommended_action="Provide or ingest an authoritative travel policy fixture.",
            repair_attempts=0,
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-missing-1",
                    stage="record",
                    outcome="FIXTURE SEEDED — empty bundle fixture",
                    recorded_at="2026-10-24T09:13:00Z",
                ),
            ),
        ),
        RunFixture(
            run_id="run-fixture-rejected",
            question="Summarize all contractor access requirements.",
            scope="Helios Remote Access Policy v2.0 (synthetic fixture)",
            state=EvidenceState.MISSING,
            status=RunStatus.FAILED,
            created_at="2026-10-24T09:14:00Z",
            summary=(
                "The fixture run failed closed after one bounded repair and abstained. No "
                "answer is displayed."
            ),
            diagnostic=(
                "Fixture validation failure: the synthetic quote could not be mapped "
                "uniquely. Authorization and integrity failures are never repaired."
            ),
            recommended_action="Route to the knowledge owner with the failure diagnostics.",
            repair_attempts=1,
            trace=(
                TraceEventFixture(
                    event_id="trace-fixture-rejected-1",
                    stage="validation",
                    outcome="FIXTURE RECORD — validation failure and safe abstention",
                    recorded_at="2026-10-24T09:14:00Z",
                ),
            ),
            error=(
                "The fixture run failed closed after one bounded repair attempt. Raw "
                "candidate output is withheld from reviewer mode."
            ),
        ),
    )

    documents = (
        DocumentFixture(
            doc_id="doc-helios-access",
            title=access_title,
            authority="Internal policy (synthetic fixture)",
            owner="Identity & Access team (fixture)",
            versions=(
                DocumentVersionFixture(
                    version_id="version-access-v1",
                    label="v1.0",
                    status=VersionStatus.SUPERSEDED,
                    effective_from="2024-01-01",
                    effective_to="2026-02-28",
                    acl_roles=("reviewer", "auditor"),
                    digest_label="FIXTURE — digest not computed",
                    chunk_ids=("chunk-access-v1-legacy",),
                ),
                DocumentVersionFixture(
                    version_id="version-access-v2",
                    label="v2.0",
                    status=VersionStatus.ACTIVE,
                    effective_from="2026-03-01",
                    supersedes="v1.0",
                    acl_roles=("reviewer", "auditor"),
                    digest_label="FIXTURE — digest not computed",
                    chunk_ids=(
                        "chunk-access-v2-mfa",
                        "chunk-access-v2-reviews",
                        "chunk-access-v2-scanned",
                    ),
                ),
            ),
        ),
        DocumentFixture(
            doc_id="doc-retention-global",
            title=retention_global_title,
            authority="Records standard (synthetic fixture)",
            owner="Records Management (fixture)",
            versions=(
                DocumentVersionFixture(
                    version_id="version-retention-global-v21",
                    label="v2.1",
                    status=VersionStatus.ACTIVE,
                    effective_from="2025-06-01",
                    acl_roles=("reviewer", "auditor"),
                    digest_label="FIXTURE — digest not computed",
                    chunk_ids=("chunk-retention-seven",),
                ),
            ),
        ),
        DocumentFixture(
            doc_id="doc-retention-regional",
            title=retention_regional_title,
            authority="Regional addendum (synthetic fixture)",
            owner="Regional Compliance (fixture)",
            versions=(
                DocumentVersionFixture(
                    version_id="version-retention-regional-v14",
                    label="v1.4",
                    status=VersionStatus.ACTIVE,
                    effective_from="2025-09-01",
                    acl_roles=("reviewer", "auditor"),
                    digest_label="FIXTURE — digest not computed",
                    chunk_ids=("chunk-retention-ten",),
                ),
            ),
        ),
    )

    escalations = (
        EscalationFixture(
            case_id="case-fixture-conflict-001",
            run_id="run-fixture-conflicted",
            reason="CONFLICTED",
            status="OPEN",
            reviewer="reviewer.fixture",
            owner="knowledge-owner.fixture",
            opened_at="2026-10-24T09:15:00Z",
            decision="PENDING",
            rationale=(
                "No fixture precedence rule settles the retention conflict. A knowledge "
                "owner must record a decision."
            ),
            audit_events=(
                EscalationEventFixture(
                    event_id="evt-fixture-001",
                    occurred_at="2026-10-24T09:15:00Z",
                    actor="system",
                    actor_role="system",
                    action="escalation.opened",
                    from_status="NONE",
                    to_status="OPEN",
                    detail=(
                        "Created from run-fixture-conflicted after the simulated fixture "
                        "conflict path."
                    ),
                ),
                EscalationEventFixture(
                    event_id="evt-fixture-002",
                    occurred_at="2026-10-24T09:16:30Z",
                    actor="reviewer.fixture",
                    actor_role="reviewer",
                    action="case.assigned",
                    from_status="OPEN",
                    to_status="OPEN",
                    detail="Assigned to a knowledge owner; no decision recorded yet.",
                ),
                EscalationEventFixture(
                    event_id="evt-fixture-003",
                    occurred_at="2026-10-24T09:17:00Z",
                    actor="auditor.fixture",
                    actor_role="auditor",
                    action="artifact.reviewed",
                    from_status="OPEN",
                    to_status="OPEN",
                    detail=(
                        "Auditor-only artifact reference retained outside reviewer mode; no "
                        "raw content is rendered here."
                    ),
                ),
            ),
        ),
    )

    return WorkbenchState(
        adjudicate=AdjudicateFixture(
            run_id="run-fixture-supported",
            scope="Helios Remote Access Policy v2.0 (synthetic fixture)",
        ),
        runs=runs,
        documents=documents,
        escalations=escalations,
        sources=sources,
    )


__all__ = [
    "FIXTURE_BADGE",
    "FIXTURE_BANNER",
    "OFFSET_WARNING",
    "UNSUPPORTED_MAP_LABEL",
    "AdjudicateFixture",
    "ClaimFixture",
    "DocumentFixture",
    "DocumentVersionFixture",
    "EscalationEventFixture",
    "EscalationFixture",
    "MapStatus",
    "RunChunkFixture",
    "RunFixture",
    "RunStatus",
    "SourceFixture",
    "TraceEventFixture",
    "VersionStatus",
    "WorkbenchState",
    "build_fixture_state",
]
