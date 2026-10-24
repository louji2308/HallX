from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from hallx.errors import ErrorCode
from hallx.inference import (
    GenerationRequest,
    GenerationResponse,
    InferenceError,
    InferenceErrorCode,
)
from hallx.models import (
    DocumentStatus,
    EvidenceChunk,
    EvidenceState,
    GenerationProofEnvelope,
)
from hallx.orchestration import Orchestrator
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

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads((ROOT / "configs" / "proof_envelope_schema.json").read_text(encoding="utf-8"))


class FakeGenerator:
    def __init__(self, outputs: list[str | Exception]) -> None:
        self.outputs = list(outputs)
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.requests.append(request)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return GenerationResponse(
            raw_text=output,
            model_id="fake-model",
            adapter_id="fake-adapter",
            request_id=f"request-{len(self.requests)}",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            elapsed_ms=float(len(self.requests)),
        )


def _candidate_json(candidate: GenerationProofEnvelope) -> str:
    return candidate.model_dump_json()


def _supported_candidate(chunk: EvidenceChunk) -> GenerationProofEnvelope:
    return make_candidate(
        claims=(make_claim(chunk),),
        triage=(make_triage(chunk),),
        state=EvidenceState.SUPPORTED,
    )


def _repairable_candidate(chunk: EvidenceChunk) -> GenerationProofEnvelope:
    return make_candidate(
        claims=(
            make_claim(
                chunk,
                claim_text="The retention period is 30 days.",
                exact_quote="quote that is absent",
            ),
        ),
        triage=(make_triage(chunk),),
        state=EvidenceState.SUPPORTED,
    )


def test_orchestration_accepts_server_state_not_model_state(schema: dict) -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    candidate = _supported_candidate(chunk).model_copy(
        update={"evidence_state": EvidenceState.MISSING}
    )
    generator = FakeGenerator([_candidate_json(candidate)])
    orchestrator = Orchestrator(generator, schema=schema)

    result = orchestrator.answer(
        "How long is retention?",
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )

    assert result.accepted is True
    assert result.envelope is not None
    assert result.final_state is EvidenceState.SUPPORTED
    assert result.envelope.evidence_state is EvidenceState.SUPPORTED
    assert result.validation.model_state is EvidenceState.MISSING
    assert result.validation.model_state_matches is False
    assert result.repairs_used == 0
    assert len(result.attempts) == 1
    assert result.attempts[0].request_id == "request-1"
    assert len(generator.requests) == 1
    assert chunk.canonical_text in generator.requests[0].messages[1].content


def test_orchestration_repairs_at_most_once(schema: dict) -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    generator = FakeGenerator(
        [
            _candidate_json(_repairable_candidate(chunk)),
            _candidate_json(_supported_candidate(chunk)),
        ]
    )
    orchestrator = Orchestrator(generator, schema=schema)

    result = orchestrator.answer(
        "How long is retention?",
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )

    assert result.accepted is True
    assert result.repairs_used == 1
    assert len(result.attempts) == 2
    assert len(generator.requests) == 2
    assert result.attempts[0].validation.repair_allowed is True
    assert result.attempts[1].validation.accepted is True
    assert result.envelope is not None

    original = generator.requests[0]
    repaired = generator.requests[1]
    assert repaired.messages[0] == original.messages[0]
    assert repaired.messages[-1].content.startswith(original.messages[-1].content)
    context = repaired.messages[-1].content.split("REPAIR_CONTEXT_JSON:\n", 1)[1]
    repair_context = json.loads(context)
    assert repair_context["repair_round"] == 1
    assert "QUOTE_NOT_FOUND" in {
        item["code"] for item in repair_context["validation_issues"]
    }
    assert repaired.response_schema == original.response_schema
    assert "tools" not in repaired.model_dump()


def test_orchestration_second_invalid_abstains(schema: dict) -> None:
    chunk = make_evidence_chunk()
    bundle = make_bundle((chunk,))
    bad = _candidate_json(_repairable_candidate(chunk))
    generator = FakeGenerator([bad, bad])
    orchestrator = Orchestrator(generator, schema=schema)

    result = orchestrator.answer(
        "How long is retention?",
        bundle,
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )

    assert result.accepted is False
    assert result.envelope is None
    assert result.final_state is EvidenceState.MISSING
    assert result.repairs_used == 1
    assert len(result.attempts) == 2
    assert len(generator.requests) == 2
    assert result.validation.repair_allowed is False
    assert ErrorCode.QUOTE_NOT_FOUND in {item.code for item in result.validation.issues}


def test_orchestration_security_failures_not_repaired(schema: dict) -> None:
    principal = make_principal()
    entailment = StaticEntailmentVerifier()

    restricted = make_evidence_chunk(acl_roles=("admin",))
    acl_generator = FakeGenerator([])
    acl_result = Orchestrator(acl_generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((restricted,)),
        principal,
        as_of=AS_OF,
        entailment=entailment,
    )
    assert len(acl_generator.requests) == 0
    assert acl_result.attempts == ()
    assert acl_result.repairs_used == 0
    assert acl_result.envelope is None
    assert ErrorCode.ACL_DENIED in {item.code for item in acl_result.validation.issues}
    assert acl_result.validation.repair_allowed is False

    identity_chunk = make_evidence_chunk()
    identity_candidate = make_candidate(
        claims=(make_claim(identity_chunk, version="v2"),),
        triage=(make_triage(identity_chunk),),
    )
    identity_generator = FakeGenerator([_candidate_json(identity_candidate)])
    identity_result = Orchestrator(identity_generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((identity_chunk,)),
        principal,
        as_of=AS_OF,
        entailment=entailment,
    )
    assert len(identity_generator.requests) == 1
    assert identity_result.repairs_used == 0
    assert identity_result.envelope is None
    assert ErrorCode.SOURCE_IDENTITY_MISMATCH in {
        item.code for item in identity_result.validation.issues
    }
    assert identity_result.validation.repair_allowed is False

    fresh_chunk = make_evidence_chunk(
        effective_from=date(2025, 1, 1),
        effective_until=date(2025, 12, 31),
    )
    fresh_candidate = _supported_candidate(fresh_chunk)
    fresh_generator = FakeGenerator([_candidate_json(fresh_candidate)])
    fresh_result = Orchestrator(fresh_generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((fresh_chunk,)),
        principal,
        as_of=AS_OF,
        entailment=entailment,
    )
    assert len(fresh_generator.requests) == 1
    assert fresh_result.repairs_used == 0
    assert fresh_result.envelope is None
    assert ErrorCode.SOURCE_EXPIRED in {item.code for item in fresh_result.validation.issues}
    assert fresh_result.validation.repair_allowed is False

    stale_chunk = make_evidence_chunk(
        "chunk-stale",
        status=DocumentStatus.SUPERSEDED,
        text="Old policy: retention is 30 days.",
    )
    stale_candidate = make_candidate(
        claims=(make_claim(stale_chunk),),
        triage=(),
        state=EvidenceState.STALE,
    )
    stale_generator = FakeGenerator([_candidate_json(stale_candidate)])
    stale_result = Orchestrator(stale_generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((), stale_candidates=(stale_chunk,)),
        principal,
        as_of=AS_OF,
        entailment=entailment,
    )
    assert len(stale_generator.requests) == 1
    assert stale_result.repairs_used == 0
    assert stale_result.envelope is None
    assert ErrorCode.SOURCE_STALE in {item.code for item in stale_result.validation.issues}
    assert stale_result.validation.repair_allowed is False


def test_orchestration_rejected_has_no_envelope(schema: dict) -> None:
    chunk = make_evidence_chunk()
    candidate = make_candidate(
        claims=(make_claim(chunk).model_copy(update={"chunk_id": "chunk-x"}),),
        triage=(make_triage(chunk),),
    )
    generator = FakeGenerator([_candidate_json(candidate)])
    result = Orchestrator(generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((chunk,)),
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )

    assert result.accepted is False
    assert result.envelope is None
    assert result.final_state is EvidenceState.MISSING
    assert result.validation.accepted is False
    assert result.repairs_used == 0
    assert len(generator.requests) == 1


def test_orchestration_rejects_malformed_json_without_repair(schema: dict) -> None:
    chunk = make_evidence_chunk()
    generator = FakeGenerator(["not-json"])
    result = Orchestrator(generator, schema=schema).answer(
        "How long is retention?",
        make_bundle((chunk,)),
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )

    assert result.accepted is False
    assert result.envelope is None
    assert result.final_state is EvidenceState.MISSING
    assert result.repairs_used == 0
    assert len(result.attempts) == 1
    assert len(generator.requests) == 1
    assert ErrorCode.SCHEMA_INVALID in {item.code for item in result.validation.issues}


def test_orchestration_caps_max_repairs(schema: dict) -> None:
    with pytest.raises(ValueError):
        Orchestrator(FakeGenerator([]), schema=schema, max_repairs=2)
    with pytest.raises(ValueError):
        Orchestrator(FakeGenerator([]), schema=schema, max_repairs=-1)

    chunk = make_evidence_chunk()
    generator = FakeGenerator([_candidate_json(_repairable_candidate(chunk))])
    result = Orchestrator(generator, schema=schema, max_repairs=0).answer(
        "How long is retention?",
        make_bundle((chunk,)),
        make_principal(),
        as_of=AS_OF,
        entailment=StaticEntailmentVerifier(),
    )
    assert result.accepted is False
    assert result.repairs_used == 0
    assert len(generator.requests) == 1
    assert result.validation.repair_allowed is True


def test_orchestration_generator_failure_propagates_without_fallback(schema: dict) -> None:
    generator = FakeGenerator(
        [InferenceError(InferenceErrorCode.TRANSPORT_FAILED, "loopback refused")]
    )
    orchestrator = Orchestrator(generator, schema=schema)
    with pytest.raises(InferenceError) as exc_info:
        orchestrator.answer(
            "How long is retention?",
            make_bundle((make_evidence_chunk(),)),
            make_principal(),
            as_of=AS_OF,
            entailment=StaticEntailmentVerifier(),
        )
    assert exc_info.value.code is InferenceErrorCode.TRANSPORT_FAILED
    assert len(generator.requests) == 1
