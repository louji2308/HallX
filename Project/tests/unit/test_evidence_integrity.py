import hashlib

from hallx.errors import ErrorCode
from hallx.models import DocumentStatus, EvidenceBundle, EvidenceState
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


def test_canonicalization_mismatch_rejects() -> None:
    chunk = make_evidence_chunk()
    forged_text = chunk.canonical_text + " extra"
    forged = chunk.model_copy(
        update={
            "canonical_text": forged_text,
            "canonical_sha256": hashlib.sha256(forged_text.encode("utf-8")).hexdigest(),
        }
    )
    bundle = make_bundle((forged,))
    candidate = make_candidate(triage=(make_triage(forged),))
    outcome = validate_envelope(
        candidate, bundle, make_principal(), as_of=AS_OF, entailment=StaticEntailmentVerifier()
    )
    assert not outcome.accepted
    codes = {item.code for item in outcome.result.issues}
    assert ErrorCode.CANONICALIZATION_MISMATCH in codes


def test_chunk_hash_mismatch_rejects() -> None:
    chunk = make_evidence_chunk()
    forged = chunk.model_copy(update={"canonical_sha256": "0" * 64})
    bundle = EvidenceBundle.model_construct(
        bundle_id="bundle-1",
        snapshot_id="snapshot-1",
        tenant_id="tenant-a",
        chunks=(forged,),
        conflict_pairs=(),
        stale_candidates=(),
    )
    outcome = validate_envelope(
        make_candidate(triage=(make_triage(forged),)),
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.CHUNK_HASH_MISMATCH in {item.code for item in outcome.result.issues}


def test_tenant_mismatch_rejects() -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    outcome = validate_envelope(
        make_candidate(triage=(make_triage(chunk),)),
        bundle,
        make_principal(tenant_id="tenant-b"),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.TENANT_MISMATCH in {item.code for item in outcome.result.issues}


def test_incomplete_triage_is_repairable() -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    outcome = validate_envelope(
        make_candidate(triage=()),
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.TRIAGE_INCOMPLETE in {item.code for item in outcome.result.issues}
    assert outcome.result.repair_allowed is True


def test_unknown_chunk_rejects_without_repair() -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    claim = make_claim(chunk).model_copy(update={"chunk_id": "chunk-x"})
    outcome = validate_envelope(
        make_candidate(claims=(claim,), triage=(make_triage(chunk),)),
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.UNKNOWN_CHUNK in {item.code for item in outcome.result.issues}
    assert outcome.result.repair_allowed is False


def test_stale_claim_rejects_without_repair() -> None:
    stale = make_evidence_chunk(
        status=DocumentStatus.SUPERSEDED,
        text="Old policy: retention is 30 days.",
    )
    bundle = make_bundle((), stale_candidates=(stale,))
    outcome = validate_envelope(
        make_candidate(claims=(make_claim(stale),), state=EvidenceState.STALE),
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert not outcome.accepted
    assert ErrorCode.SOURCE_STALE in {item.code for item in outcome.result.issues}
    assert outcome.result.repair_allowed is False


def test_false_entailment_rejects() -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    outcome = validate_envelope(
        make_candidate(claims=(make_claim(chunk),), triage=(make_triage(chunk),)),
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(entailed=False),
    )
    assert not outcome.accepted
    assert ErrorCode.CITATION_NOT_ENTAILED in {item.code for item in outcome.result.issues}
    assert outcome.result.repair_allowed is True
