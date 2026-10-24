import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hallx.models import GenerationProofEnvelope
from tests.support import make_candidate, make_claim, make_evidence_chunk, make_triage

ROOT = Path(__file__).resolve().parents[2]


def test_generation_schema_has_no_offsets() -> None:
    schema_text = json.dumps(GenerationProofEnvelope.model_json_schema())
    assert "char_start" not in schema_text
    assert "char_end" not in schema_text
    assert "original_char_start" not in schema_text
    assert "original_char_end" not in schema_text


def test_generation_schema_rejects_model_supplied_offsets() -> None:
    chunk = make_evidence_chunk()
    candidate = make_candidate(
        claims=(make_claim(chunk),),
        triage=(make_triage(chunk),),
    )
    payload = candidate.model_dump()
    payload["claims"][0]["char_start"] = 0
    payload["claims"][0]["char_end"] = 5
    with pytest.raises(ValidationError):
        GenerationProofEnvelope.model_validate(payload)


def test_committed_schema_matches_models() -> None:
    path = ROOT / "configs" / "proof_envelope_schema.json"
    assert path.exists(), "run scripts/export_generation_schema.py"
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == GenerationProofEnvelope.model_json_schema()
