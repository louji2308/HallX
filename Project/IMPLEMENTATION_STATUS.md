# HallX-Local implementation status

**Last updated:** 2026-10-24
**Repo root:** `C:\Users\LOUJAN B\HallX`
**Git:** dedicated repository; branch `main`; remote `https://github.com/louji2308/HallX.git`; Phase 1 commits `09e3205` and `28dff15`, pushed. Phase 2 implementation is `1903f1b`; this report/status update is an immediate follow-up commit.

## Phase status

| Phase | Status | Evidence / note |
|---|---|---|
| P0 Repository and environment audit | `implemented` | Environment inventory and dedicated repository isolation complete; formal `reports/phase-0.md` not written yet. |
| P1 Contracts and deterministic core | `tested` | `reports/phase-1.md`; 35 unit tests pass; generation schema frozen. |
| P2 Corpus registry, versions, and ACL policy | `tested` | `reports/phase-2.md`; 53-test gate and 87-test full suite pass; Phase 2-scope lint passes; implementation commit `1903f1b`. |
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

## P2 implemented and tested

- Local SQLite corpus registry with checksum-verified, idempotent schema migration.
- Server-resolved principals and roles; deny-by-default document ACLs; live recheck on every content read.
- Immutable document/version/chunk content; append-only activation events; derived draft/active/superseded/expired status.
- Explicit immutable version-pair precedence rules; unresolved and ambiguous conflicts fail closed.
- Family-level split assignment with four split names, split-lock hash, duplicate-source rejection, and train-only guard.
- Deterministic snapshot manifest with separate content and split-lock SHA-256 values; closed-set snapshot authorization.
- Append-only audit rows with allow-listed metadata; no sentinel text in errors, audit metadata, or evidence logs.
- `.gitignore` protects local databases and corpus data.

## Commands actually run

```powershell
# Phase 1
uv lock                                   # exit 0: resolved 12 packages
uv sync --frozen                          # exit 0: checked 12 packages
uv run pytest tests/unit -q               # exit 0: 35 passed in 0.45s
uv run pytest -q                          # exit 0: 35 passed in 0.44s
uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')"  # exit 0

# Phase 2
uv sync --frozen                          # exit 0: checked 12 packages
uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"  # exit 0: 53 passed, 34 deselected
uv run pytest tests/unit tests/security --collect-only -q -k "corpus or acl or version or snapshot"  # exit 0: 53/87 collected
uv run pytest tests/unit -q               # exit 0: 74 passed
uv run pytest -q                          # exit 0: 87 passed
uv run python -c "from hallx.corpus import CorpusRegistry, migrate; print('import-ok')"  # exit 0
uv run ruff check <Phase 2 paths>         # exit 0: all checks passed
```

Environment: Python 3.11.9, SQLite 3.45.1, `uv` 0.12.3, pydantic 2.14.1, pytest 8.4.2, ruff 0.16.0, Windows. No GPU used; `nvidia-smi` absent.

## Known failures / blockers

- No known Phase 1 or Phase 2 test failures. Real entailment scoring is not implemented and is not claimed. Phase 1 proves deterministic plumbing with a test double.
- Repository-wide `uv run ruff check` still reports 21 pre-existing findings in frozen Phase 1 files and Phase 1 test helpers. Phase 2-scoped lint passes; those files were not edited per the frozen P1 contract.
- No API, UI, retrieval, ingestion, SGLang, training, evaluation, latency, accuracy, or judge-score result exists.
- `require_train_only(snapshot_id, family_ids)` has no actor parameter in the frozen contract; callers must pass a snapshot already resolved within their tenant.
- `reports/phase-0.md` is still missing; P0 remains recorded as `implemented` without a formal report.
- Target pins are unchanged: SGLang 0.5.22, CuratorKIT 1.0.0, AlignTune 0.1.28, AuditKIT 1.0.0, Qwen3-4B-Instruct-2507.

## Licensing

CuratorKIT and AuditKIT have not been installed or used. Their LSAL source-available terms, third-party notices, and the MinerU AGPL-3.0 caveat remain outstanding for Phases 6–8.

## Next exit gate

Phase 3: ingestion, canonical source maps, ACL-first retrieval, deterministic evidence bundle, and retrieval trace. Phase 3 must consume the Phase 2 `authorize_chunk`/`authorized_chunks` API, recheck live ACL, and prove that no draft, stale, cross-tenant, or ungranted source can enter retrieval or a bundle. No SGLang or GPU path exists yet.
