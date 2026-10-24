# Phase 1 — Contracts and deterministic core

**Date:** 2026-10-24
**Contract:** `reports/contracts/P1-contracts-and-deterministic-core.md` v1 (frozen)
**Status:** verified; committed and pushed to `origin/main`

## Objective

Make the evidence truth boundary executable without a GPU, network, or live LLM. The server parses a candidate `ProofEnvelope`, checks it against frozen evidence, computes canonical offsets, and resolves the final five-state result.

## Delivered

- Python 3.11 package `hallx` with `uv`/pytest scaffold and `uv.lock`.
- Frozen Pydantic v2 models for documents, versions, chunks, snapshots, principals, evidence bundles, generation envelopes, validated claims, validation results, and outcomes.
- Generation schema exported to `configs/proof_envelope_schema.json`; it contains no character offsets.
- `nfkc-ws-v1` canonicalization with per-character source maps and SHA-256.
- Unique exact-quote resolver; empty, missing, and ambiguous quotes fail closed.
- Numeric/unit consistency guard.
- Pre-model bundle validation for tenant, ACL, active status, canonicalization version, content hash, and source-map support.
- Server-owned five-state resolver (`SUPPORTED`, `PARTIAL`, `MISSING`, `CONFLICTED`, `STALE`) with server-composed summary and diagnostics.
- Independent entailment-verifier protocol. The production verifier is not wired yet; absence fails closed. Tests use an explicit `StaticEntailmentVerifier` and do not claim a real NLI result.
- One-repair policy encoded as `repair_allowed`; authorization, ACL, identity, integrity, stale, ambiguity, and conflict failures are never repairable.
- 35 unit tests covering the nine required Phase 1 cases and additional integrity paths.

## Commands and results

| Command | Exit | Result |
|---|---|---|
| `uv lock` | 0 | Resolved 12 packages; wrote `uv.lock` |
| `uv sync --frozen` | 0 | Checked 12 packages |
| `uv run pytest tests/unit -q` | 0 | 35 passed in 0.45s |
| `uv run pytest -q` | 0 | 35 passed in 0.44s |
| `uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')"` | 0 | `import-ok` |

Environment: Windows 10/11 host, Python 3.11.9, `uv` 0.12.3, pydantic 2.14.1, pytest 8.4.2. No GPU was used. `nvidia-smi` was not run because no GPU is present on this host.

## Required nine cases

| Case | Test | Result |
|---|---|---|
| Supported | `test_required_cases.py::test_supported` | pass |
| Partial | `test_required_cases.py::test_partial_names_missing_information` | pass |
| Missing | `test_required_cases.py::test_missing_has_no_factual_claims` | pass |
| Conflicted | `test_required_cases.py::test_conflicted_preserves_both_sources` | pass |
| Stale | `test_required_cases.py::test_stale_cannot_be_supported` | pass |
| Duplicate quote | `test_required_cases.py::test_duplicate_quote_fails_closed` | pass |
| Numeric mismatch | `test_required_cases.py::test_numeric_mismatch_rejects` | pass |
| Access denial | `test_required_cases.py::test_access_denial_rejects` | pass |
| Injected text | `test_required_cases.py::test_injected_text_is_not_authority` | pass |

Additional invariant tests cover schema offset rejection, source-map mapping/failure, model-state override rejection, tenant mismatch, hash mismatch, canonicalization mismatch, incomplete triage, unknown chunk, stale citation, false entailment, and the second-repair stop.

## Evidence

- `reports/evidence/p1/logs/uv-sync.txt`
- `reports/evidence/p1/logs/pytest.txt`
- `reports/evidence/p1/logs/pytest-unit.txt`
- `reports/evidence/p1/logs/import.txt`
- `configs/proof_envelope_schema.json`
  SHA-256 `72e2922bac81994b7ed0af3647e1ede94bef7040250eb5a87daa6e9ee0418700`

## Repository

- Dedicated repository: `C:\Users\LOUJAN B\HallX`, branch `main`, remote `https://github.com/louji2308/HallX.git`.
- Phase 1 commit: `09e3205` (`phase 1: contracts and deterministic evidence core`).
- Pushed to `origin/main`; no other repository was touched.

## Not proven / blocked

- Entailment is an interface plus test double only. A real independent NLI/entailment verifier is not part of Phase 1 and must not be claimed as measured.
- No API, browser, ingestion, retrieval, SGLang, or UI work was performed or claimed.
- No performance, accuracy, or judge-score metrics were measured.

## End-of-phase block

```text
PHASE: P1 contracts and deterministic core
STATUS: verified
CONTRACT: reports/contracts/P1-contracts-and-deterministic-core.md v1
CHANGED: AGENTS.md, pyproject.toml, uv.lock, .gitignore, configs/track_manifest.yaml, configs/proof_envelope_schema.json, scripts/export_generation_schema.py, src/hallx/*, tests/*, reports/contracts/P1-contracts-and-deterministic-core.md, reports/phase-1.md, IMPLEMENTATION_STATUS.md
COMMIT: 09e3205 phase 1: contracts and deterministic evidence core; pushed to origin/main
COMMANDS:
- uv lock -> exit 0: resolved 12 packages
- uv sync --frozen -> exit 0: checked 12 packages
- uv run pytest tests/unit -q -> exit 0: 35 passed
- uv run pytest -q -> exit 0: 35 passed
- uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')" -> exit 0: import-ok
- git push -u origin main -> exit 0: main -> main
TESTS: 35 passed/0 failed/0 skipped; invariants: test_schema.py::test_generation_schema_has_no_offsets, test_span.py::test_unique_quote_resolves, test_state.py::test_model_state_cannot_override_server_state, test_canonical.py::test_source_map_span_and_failure
BROWSER: not applicable (no UI in Phase 1)
ARTIFACTS: reports/evidence/p1/logs/*; configs/proof_envelope_schema.json sha256=72e2922bac81994b7ed0af3647e1ede94bef7040250eb5a87daa6e9ee0418700
BLOCKED/NOT PROVEN: real entailment verifier not wired; no GPU/server/e2e
NEXT: Phase 2 (corpus registry, versions, and ACL policy) unblocked
```
