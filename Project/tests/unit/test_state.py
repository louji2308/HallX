from hallx.errors import ErrorCode, Severity
from hallx.models import EvidenceState
from hallx.validation import validate_envelope
from tests.support import (
    AS_OF,
    StaticEntailmentVerifier,
    make_bundle,
    make_candidate,
    make_claim,
    make_evidence_chunk,
    make_principal,
    make_triage,
)


def _supported_case(state: EvidenceState = EvidenceState.SUPPORTED):
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    candidate = make_candidate(
        claims=(make_claim(chunk, numeric_values=("30 days",)),),
        triage=(make_triage(chunk),),
        state=state,
    )
    return chunk, bundle, candidate


def test_model_state_cannot_override_server_state() -> None:
    chunk, bundle, candidate = _supported_case(state=EvidenceState.MISSING)
    outcome = validate_envelope(
        candidate,
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert outcome.accepted
    assert outcome.envelope is not None
    assert outcome.envelope.evidence_state is EvidenceState.SUPPORTED
    assert outcome.result.model_state is EvidenceState.MISSING
    assert outcome.result.model_state_matches is False
    warnings = [
        item for item in outcome.result.issues if item.code is ErrorCode.EVIDENCE_STATE_MISMATCH
    ]
    assert warnings and warnings[0].severity is Severity.WARNING


def test_no_entailment_verifier_fails_closed() -> None:
    _, bundle, candidate = _supported_case()
    outcome = validate_envelope(candidate, bundle, make_principal(), as_of=AS_OF)
    assert not outcome.accepted
    assert outcome.envelope is None
    codes = {item.code for item in outcome.result.issues}
    assert ErrorCode.CITATION_NOT_ENTAILED in codes
    assert outcome.result.repair_allowed is True


def test_second_repair_is_not_allowed() -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    candidate = make_candidate(
        claims=(
            make_claim(
                chunk,
                claim_text="The retention period is 90 days.",
                numeric_values=("90 days",),
            ),
        ),
        triage=(make_triage(chunk),),
    )
    outcome = validate_envelope(
        candidate,
        bundle,
        make_principal(),
        as_of=AS_OF,
        previous_repairs=1,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.NUMERIC_MISMATCH in {item.code for item in outcome.result.issues}
    assert outcome.result.repair_allowed is False
