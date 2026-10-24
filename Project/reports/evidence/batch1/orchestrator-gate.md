# Batch 1 orchestrator gate

Date: 2026-10-24
Baseline commit: a88e484 (no batch-1 commit yet)
Host: Windows, Python 3.11.9, uv 0.12.3, pydantic 2.14.1, pytest 8.4.2, ruff 0.16.0
GPU/live SGLang: not available / not attempted

## Full test suite

Command:

    uv run pytest -q

Exit code: 0

Output:

    222 passed in 22.41s

## Batch-scope lint

Command:

    uv run ruff check src/hallx/ingestion src/hallx/retrieval src/hallx/prompting src/hallx/inference src/hallx/orchestration src/hallx/workbench src/hallx/curation tests/unit/test_ingestion.py tests/unit/test_retrieval.py tests/unit/test_retrieval_sparse.py tests/unit/test_prompt.py tests/unit/test_inference.py tests/unit/test_orchestration.py tests/unit/test_workbench.py tests/unit/test_curation_config.py tests/unit/test_curation_export.py tests/unit/test_curation_checksum.py tests/unit/test_curation_safety.py tests/security/test_retrieval_acl.py tests/security/test_prompt_injection.py tests/support_ingestion.py tests/support_curation.py

Exit code: 0

Output:

    All checks passed!

## Worker evidence

- P3 ingestion: reports/evidence/p3/ingestion/
- P3 retrieval: reports/evidence/p3/retrieval/
- P4 mock-only: reports/evidence/p4/
- P5 fixture shell: reports/evidence/p5/
- P6 validators: reports/evidence/p6/

## Not proven

- PDF page mapping and P2 registry ingestion integration (P3).
- Live SGLang 0.5.22 smoke (P4).
- Chrome DevTools reviewer E2E and real P3/P4 wiring (P5).
- Real CuratorKIT generation/exports and licence verification (P6).
- Batch-1 commit/push approval.
