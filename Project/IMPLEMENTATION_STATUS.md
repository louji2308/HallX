# HallX-Local implementation status

**Last updated:** 2026-10-24
**Repo root:** `C:\Users\LOUJAN B\HallX`
**Git:** dedicated repository; branch `main`; remote `https://github.com/louji2308/HallX.git`; Phase 1 commit `09e3205`, pushed.

## Phase status

| Phase | Status | Evidence / note |
|---|---|---|
| P0 Repository and environment audit | `implemented` | Environment inventory and dedicated repository isolation complete; formal `reports/phase-0.md` not written yet. |
| P1 Contracts and deterministic core | `tested` | `reports/phase-1.md`; 35 unit tests pass; generation schema frozen. |
| P2 Corpus registry, versions, and ACL policy | `planned` | Not started. |
| P3 Ingestion, canonical source maps, and ACL-first retrieval | `planned` | Not started. |
| P4 SGLang inference integration and bounded orchestration | `planned` | Not started; no GPU on host. |
| P5 Reviewer workbench | `planned` | Not started. |
| P6 CuratorKIT curation orchestration | `planned` | Not started. |
| P7 AlignTune progressive training | `planned` | Not started; no GPU on host. |
| P8 AuditKIT evaluation and feedback loop | `planned` | Not started. |
| P9 ML Auditor workbench, demo, and release gate | `planned` | Not started. |

## P1 implemented and tested

- Frozen Pydantic models and generation schema with no model-supplied character offsets.
- `nfkc-ws-v1` canonicalization, explicit source maps, and SHA-256.
- Unique quote resolution; empty, missing, and ambiguous quotes fail closed.
- Numeric/unit consistency checks.
- Bundle checks for tenant, ACL, active status, canonicalization version, content hash, and source-map support.
- Server-owned five-state evidence resolution and server-composed summary/diagnostics.
- Entailment verifier protocol; missing verifier fails closed. Tests use an explicit test double, not a real NLI model.
- One-repair policy; security, ACL, identity, integrity, stale, ambiguity, and conflict errors are never repairable.

## Commands actually run

```powershell
uv lock                                   # exit 0: resolved 12 packages
uv sync --frozen                          # exit 0: checked 12 packages
uv run pytest tests/unit -q               # exit 0: 35 passed in 0.45s
uv run pytest -q                          # exit 0: 35 passed in 0.44s
uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')"  # exit 0
```

Environment: Python 3.11.9, `uv` 0.12.3, pydantic 2.14.1, pytest 8.4.2, Windows. No GPU used; `nvidia-smi` absent.

## Known failures / blockers

- No known test failures. Real entailment scoring is not implemented and is not claimed. Phase 1 proves deterministic plumbing with a test double.
- No API, UI, retrieval, ingestion, SGLang, training, evaluation, latency, accuracy, or judge-score result exists.
- Target pins are unchanged: SGLang 0.5.22, CuratorKIT 1.0.0, AlignTune 0.1.28, AuditKIT 1.0.0, Qwen3-4B-Instruct-2507.

## Licensing

CuratorKIT and AuditKIT have not been installed or used. Their LSAL source-available terms, third-party notices, and the MinerU AGPL-3.0 caveat remain outstanding for Phases 6–8.

## Next exit gate

Phase 2: SQLite corpus registry with immutable versions, temporal validity, authority/precedence, deny-by-default ACLs, and a reproducible snapshot manifest. Gate: `uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"` with revoked-ACL, cross-workspace, superseded-version, active-conflict, integrity-mismatch, and snapshot-immutability cases. No retrieval or SGLang call exists in Phase 2.
