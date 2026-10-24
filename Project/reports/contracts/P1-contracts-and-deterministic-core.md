# P1 — contracts and deterministic core contract v1

OWNER: orchestrator
STATUS: frozen for Phase 1
SOURCE OF TRUTH: `IDEA.md` §§7, 10, 14; `ARCHITECTURE.md` §§4, 5, 7, 8, 14; `WORKFLOWS.md` §§2, 3, 13; this contract.

## Objective

Make the evidence truth boundary executable without a GPU, network, or live LLM. A candidate `ProofEnvelope` is parsed, checked against frozen evidence, and either validated or rejected. The server owns canonicalization, quote resolution, offsets, source identity, freshness, ACL checks, and the final evidence state.

## In scope

- Python package scaffold `src/hallx/` with Python 3.11+, `uv`, pytest.
- Generation-time and validated `ProofEnvelope` models.
- Document/version/chunk/corpus-snapshot/evidence-bundle models.
- Canonicalization `nfkc-ws-v1` with explicit source maps and SHA-256.
- Unique exact-quote resolver, numeric/unit checks, source identity/status/freshness/ACL checks.
- Five-state evidence resolver and cross-field consistency checks.
- One independent-entailment interface; the production verifier is wired in Phase 4. Phase 1 tests use an explicit test double and do not claim a real NLI result.
- Unit tests for supported, partial, missing, conflicted, stale, duplicate quote, numeric mismatch, access denial, and injected text.
- Machine-readable generation schema at `configs/proof_envelope_schema.json`.

## Out of scope

- SQLite persistence, ingestion, retrieval, PDF parsing, SGLang calls, UI, CuratorKIT, AlignTune, AuditKIT.
- Real entailment scoring, model training, evaluation metrics, demo claims.
- Any external API, cloud call, telemetry, or network access.

## Frozen interfaces

### Enums

`EvidenceState = SUPPORTED | PARTIAL | MISSING | CONFLICTED | STALE`

`ClaimSupportStatus = SUPPORTED | PARTIAL`

`TriageStatus = RELEVANT_ACTIVE | DISTRACTOR_IRRELEVANT | SUPERSEDED_STALE | RESTRICTED_ACL | ADVERSARIAL_IGNORED`

`DocumentStatus = ACTIVE | SUPERSEDED | EXPIRED | DRAFT`

### Generation-time schema

Field names are exactly those in `IDEA.md` §7, with one binding deletion: claims must not contain `char_start` or `char_end`.

```
GenerationProofEnvelope:
  chunk_triage: list[GenerationChunkTriage]
  evidence_state: EvidenceState
  answer_summary: str
  claims: list[GenerationClaim]
  abstention_and_conflict_diagnosis: AbstentionAndConflictDiagnosis
  human_review_required: bool

GenerationChunkTriage:
  chunk_id, doc_id, version, triage_status, triage_reason

GenerationClaim:
  claim_text, support_status, chunk_id, doc_id, version,
  exact_quote, numeric_values, claim_to_quote_rationale

AbstentionAndConflictDiagnosis:
  missing_information, rejected_distractor_chunk_ids,
  conflicting_chunk_ids, stale_chunk_ids, recommended_human_action
```

All models use `extra="forbid"` and are frozen.

### Validated schema

`ValidatedProofEnvelope` contains the generation fields plus:

```
claims: list[ValidatedClaim]
ValidatedClaim = GenerationClaim fields + char_start, char_end,
                 original_char_start, original_char_end,
                 canonical_sha256, source_sha256,
                 page_start, page_end,
                 entailment_verifier_id, entailment_score
validation_result: ValidationResult
```

`char_start`/`char_end` are Unicode character offsets into the cited chunk's canonical text. `original_char_start`/`original_char_end` are Unicode character offsets into the chunk's original extracted text. They are server-computed. A model-supplied offset is a schema error.

```
ValidationResult:
  accepted: bool
  final_state: EvidenceState | None
  model_state: EvidenceState
  model_state_matches: bool
  issues: list[ValidationIssue]
  repair_allowed: bool
  final_human_review_required: bool
  canonicalization_version: str
  schema_version: str
```

### Canonicalization

`CANONICALIZATION_VERSION = "nfkc-ws-v1"`

- Whitespace runs collapse to one ASCII space.
- Each non-whitespace Unicode character is NFKC-normalized per character; expansions map to the original character's range.
- SHA-256 is over the canonical UTF-8 text.
- `CanonicalDocument.to_original_span(start, end)` must map any valid canonical span to an original span or raise `SourceMapError`.
- No canonicalization may silently reuse offsets from a different version.

### Signatures

```python
canonicalize(raw_text: str) -> CanonicalDocument

resolve_unique_quote(canonical_text: str, quote: str) -> tuple[int, int]
# raises SpanResolutionError(code=QUOTE_EMPTY | QUOTE_NOT_FOUND | QUOTE_AMBIGUOUS)

check_numeric_consistency(
    claim_text: str, exact_quote: str, declared_values: Sequence[str]
) -> tuple[NumericMismatch, ...]

validate_evidence_bundle(
    bundle: EvidenceBundle, principal: Principal
) -> tuple[ValidationIssue, ...]

validate_envelope(
    candidate: GenerationProofEnvelope | Mapping[str, Any],
    bundle: EvidenceBundle,
    principal: Principal,
    *,
    as_of: date,
    previous_repairs: int = 0,
    entailment: EntailmentVerifier | None = None,
) -> ValidationOutcome

class EntailmentVerifier(Protocol):
    verifier_id: str
    def check(self, *, claim_text: str, exact_quote: str,
              chunk: EvidenceChunk) -> EntailmentResult: ...
```

`validate_envelope` never mutates input models. It never trusts model offsets, state, ACL, status, or triage as authority.

### Error codes (typed, stable)

Schema and bundle: `SCHEMA_INVALID`, `BUNDLE_EMPTY`, `DUPLICATE_CHUNK_ID`, `TRIAGE_INCOMPLETE`, `TRIAGE_DUPLICATE`, `TRIAGE_UNKNOWN_CHUNK`, `TRIAGE_IDENTITY_MISMATCH`, `CHUNK_HASH_MISMATCH`, `CANONICALIZATION_MISMATCH`, `SOURCE_MAP_UNSUPPORTED`, `INTERNAL_ERROR`.

Quote and claim: `QUOTE_EMPTY`, `QUOTE_NOT_FOUND`, `QUOTE_AMBIGUOUS`, `UNKNOWN_CHUNK`, `SOURCE_IDENTITY_MISMATCH`, `CLAIM_TRIAGE_MISMATCH`, `ADVERSARIAL_EVIDENCE`, `CITATION_NOT_ENTAILED`, `NUMERIC_MISMATCH`.

Authorization and freshness: `ACL_DENIED`, `TENANT_MISMATCH`, `SOURCE_NOT_ACTIVE`, `SOURCE_STALE`, `SOURCE_EXPIRED`.

State and diagnostics: `CONFLICT_UNRESOLVED`, `CONFLICT_DIAGNOSTIC_MISSING`, `STALE_DIAGNOSTIC_MISSING`, `PARTIAL_DIAGNOSTICS_REQUIRED`, `MISSING_DIAGNOSTICS_REQUIRED`, `SUMMARY_UNSUPPORTED`, `EVIDENCE_STATE_MISMATCH` (warning only).

### Repair policy

- `repair_allowed` is true only when all blocking issues are repairable, no security/integrity/authorization issue exists, and `previous_repairs < 1`.
- Repairable: `QUOTE_NOT_FOUND`, `NUMERIC_MISMATCH`, `CITATION_NOT_ENTAILED`, `TRIAGE_INCOMPLETE`, `PARTIAL_DIAGNOSTICS_REQUIRED`, `CONFLICT_DIAGNOSTIC_MISSING`.
- Never repairable: `ACL_DENIED`, `TENANT_MISMATCH`, `SOURCE_IDENTITY_MISMATCH`, `UNKNOWN_CHUNK`, `SOURCE_NOT_ACTIVE`, `SOURCE_STALE`, `SOURCE_EXPIRED`, `ADVERSARIAL_EVIDENCE`, `QUOTE_AMBIGUOUS`, `SOURCE_MAP_UNSUPPORTED`, `CHUNK_HASH_MISMATCH`, `CANONICALIZATION_MISMATCH`, `CONFLICT_UNRESOLVED`.
- A rejected envelope is not a validated envelope. Phase 4 enforces that a repair is attempted at most once.

### Five-state resolution

The server derives the state; the model state is candidate input only.

1. Any security/integrity/identity/ACL/active-status error -> reject; no final state.
2. Unresolved active conflict pair -> `CONFLICTED`; force human review; require both conflict references in diagnostics.
3. Valid claims present, no missing information, no partial claim -> `SUPPORTED`.
4. Valid claims present with missing information or a `PARTIAL` claim -> `PARTIAL`; require non-empty missing information.
5. No valid claims and stale candidates are the only matching evidence -> `STALE`; require stale references.
6. Otherwise -> `MISSING`; require missing information, synthesizing a non-restricted server diagnostic if the model omitted it.
7. Non-`SUPPORTED` states force `human_review_required=true`. A model/server state mismatch is a recorded warning, never a model override.
8. Final `answer_summary` is composed from validated claim texts and diagnostics. Unchecked model prose is never displayed as the final summary.

## Write paths

- orchestrator -> `reports/contracts/P1-contracts-and-deterministic-core.md`, `reports/phase-1.md`, `IMPLEMENTATION_STATUS.md`
- scaffold worker -> `pyproject.toml`, `uv.lock`, `configs/track_manifest.yaml`, `configs/proof_envelope_schema.json`, `scripts/export_generation_schema.py`, `src/hallx/__init__.py`
- models worker -> `src/hallx/models.py`, `src/hallx/errors.py`
- canonical worker -> `src/hallx/canonical.py`, `src/hallx/source_map.py`
- validation worker -> `src/hallx/validation/*`
- test writer -> `tests/unit/*`, `tests/conftest.py`

No worker may edit another worker's path. The orchestrator owns merges.

## Acceptance

```powershell
uv sync --frozen
uv run pytest tests/unit -q
uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')"
```

Pass criteria:
- install succeeds from `uv.lock`;
- all unit tests pass;
- the required nine cases are present and green;
- the generation schema rejects model offsets;
- no test uses a GPU, network, or live LLM;
- every rejection carries a typed issue code.

If `uv` cannot resolve offline, the exact failure is recorded and the suite is run with the available interpreter; the `uv` command is not claimed as passed.

## Invariants/tests

| Invariant | Test id |
|---|---|
| Generation schema excludes offsets | `test_schema.py::test_generation_schema_has_no_offsets` |
| Final offsets are server-computed and unique | `test_span.py::test_unique_quote_resolves` |
| Duplicate quote fails closed and is not repairable | `test_required_cases.py::test_duplicate_quote_fails_closed` |
| Numeric/unit mismatch rejects | `test_required_cases.py::test_numeric_mismatch_rejects` |
| ACL denial rejects without repair | `test_required_cases.py::test_access_denial_rejects` |
| Stale cannot be SUPPORTED | `test_required_cases.py::test_stale_cannot_be_supported` |
| Conflict requires both sources and review | `test_required_cases.py::test_conflicted_preserves_both_sources` |
| MISSING has no factual claims | `test_required_cases.py::test_missing_has_no_factual_claims` |
| PARTIAL names missing information | `test_required_cases.py::test_partial_names_missing_information` |
| Injected text is data, never authority | `test_required_cases.py::test_injected_text_is_not_authority` |
| Server overrides model state | `test_state.py::test_model_state_cannot_override_server_state` |
| Source map proves original span or fails | `test_canonical.py::test_source_map_span_and_failure` |

## Evidence

- `reports/evidence/p1/logs/pytest.txt` (command, exit code, output)
- `reports/phase-1.md`
- `IMPLEMENTATION_STATUS.md`
- schema SHA-256 recorded in the report

## Stop/blocked

- A shortcut that puts offsets, state, ACL, or freshness authority in model output.
- An invariant that cannot be enforced deterministically.
- A dependency resolution that changes the pinned target stack.
- Git root remains the enclosing home directory: code continues, but `COMMIT` is reported as `blocked: dedicated HallX repo not established`.

## Changes

v1 initial — frozen at Phase 1 start.
