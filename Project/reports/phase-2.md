# Phase 2 — corpus registry, versions, ACL policy, split lock, and snapshots

**STATUS:** tested
**CONTRACT:** `reports/contracts/P2-corpus-and-acl.md` v1
**DATE:** 2026-10-24
**COMMIT:** `1903f1b` (`phase 2: corpus registry, versions, ACL, split lock, snapshots`); this report and status update are recorded in an immediate follow-up commit.

## Objective

Own document identity, immutable content, temporal validity, explicit precedence, deny-by-default permissions, family-level split locks, and reproducible snapshot identity before retrieval exists. Phase 2 makes unauthorized, draft, superseded, or expired content impossible to project as current evidence through the registry API.

## Delivered

- SQLite schema and checksum-verified, idempotent migration.
- Server-resolved principals and roles; no client-supplied tenant or role authority.
- Immutable document, version text, chunk, activation, precedence, snapshot, and audit rows.
- Append-only activation events and derived `DRAFT`/`ACTIVE`/`SUPERSEDED`/`EXPIRED` status.
- Explicit version-pair precedence resolution; `authority` never resolves a conflict.
- Document-level deny-by-default ACLs; revocation is live and rechecked on every content read.
- Family-level split assignment, four split names, split-lock hash, duplicate-source rejection, and train-only guard.
- Deterministic snapshot builder/verifier using domain-separated SHA-256 and canonical JSON.
- Public uniform `CORPUS_NOT_FOUND` behavior for content reads; internal authorization decisions retain diagnostic reasons.
- `.gitignore` protection for local databases and corpus data.

## Frozen decisions

- No Phase 1 model, validator, error-code, or contract change. P2 projection records wrap Phase 1 data; `EvidenceChunk` is hydrated only after authorization.
- Python standard library `sqlite3` only; no dependency added.
- `tenant_id` is the single workspace boundary. ACL is document-level only.
- `corpus_admin` manages metadata and grants but does not bypass document content ACLs.
- Snapshot content is content-only; ACL, status, titles, paths, timestamps, and row order are excluded.
- `snapshot_id = "snap-" + manifest_sha256`; content and split-lock hashes are separate.
- Public content reads use uniform not-found; audit metadata uses an allow-list of IDs, roles, hashes, dates, split names, and reason codes only.

## Spec conflict recorded

`AGENTS.md` §6 describes Phase 2 as including a deterministic evidence bundle with trace and permissions. `IMPLEMENTATION_PLAN.md` §5 gates Phase 2 only on corpus/ACL/version/snapshot, and §6 places retrieval, bundle, trace, and permissions in Phase 3. This phase follows the narrower, stricter plan: Phase 2 owns the registry, ACL service, split lock, and snapshot primitive; Phase 3 consumes the authorization API to build bundles. No spec file was edited.

## Verification evidence

Environment: Python `3.11.9`, SQLite `3.45.1`, `uv 0.12.3`, `pydantic 2.14.1`, `pytest 8.4.2`, `ruff 0.16.0`, Windows. No GPU, SGLang, network, browser, or retrieval path used.

| Command | Result |
|---|---|
| `uv sync --frozen` | exit 0; `Checked 12 packages` |
| `uv run python -c "import sys, sqlite3; print(sys.version); print(sqlite3.sqlite_version)"` | exit 0; Python 3.11.9; SQLite 3.45.1 |
| `uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"` | exit 0; **53 passed, 34 deselected** |
| `uv run pytest tests/unit tests/security --collect-only -q -k "corpus or acl or version or snapshot"` | exit 0; **53/87 collected**, 34 deselected |
| `uv run pytest tests/unit -q` | exit 0; **74 passed** |
| `uv run pytest -q` | exit 0; **87 passed** |
| `uv run python -c "from hallx.corpus import CorpusRegistry, migrate; print('import-ok')"` | exit 0; `import-ok` |
| `uv run ruff check <Phase 2 paths>` | exit 0; all checks passed |

The gate selection includes 52 Phase 2 tests plus the Phase 1 test `test_canonicalization_version_is_pinned`, which matches the `version` filter. Full-suite count is 35 Phase 1 tests plus 52 Phase 2 tests.

Repository-wide `uv run ruff check` reports 21 pre-existing findings in frozen Phase 1 files (`src/hallx/canonical.py`, `src/hallx/models.py`, `src/hallx/source_map.py`, `src/hallx/validation/**`, `tests/support.py`, `tests/unit/test_state.py`). Phase 2 did not edit those files; Phase 2-scoped lint is clean. This is recorded as a known issue rather than presented as a passing repository-wide gate.

## Invariant coverage

- Migrations: idempotent apply, checksum mismatch, unsupported future version, foreign keys.
- Version lifecycle: immutable rows, draft hidden, inclusive effective boundaries, expiry, future-not-fresh, supersession without predecessor mutation, fork/cross-document rejection, overlap rejection, idempotent activation, canonical-text rejection.
- Fresh/stale projection: authorized chunks exclude draft, future, superseded, and expired versions; `stale_chunks` returns superseded/expired chunks explicitly.
- Conflicts: unresolved active pair, explicit winner, opposite-rule ambiguity, authority alone does not resolve, stale pair is not a conflict.
- Splits: one family per split, family leakage, duplicate source across splits, lock prevents reassignment, train-only guard.
- Snapshots: reproducible across insertion order and DB path, content/split hash independence, closed set (including source-open), immutable rows, tampered manifest/live hash detection, missing document/version rejection.
- ACL/security: deny by default, revoke after prior read, source-open recheck, cross-workspace uniform not-found, guessed restricted chunk not hydrated, admin no content bypass, forged bundle ACL cannot override live ACL, ACL re-grant reauthorizes, snapshot-boundary denials audited, no sentinel text in errors or audit metadata.
- Audit: mutation rows, append-only behavior, metadata allow-list.

## Evidence layout

```text
reports/evidence/p2/logs/{uv-sync,pytest-gate,pytest-gate-rerun,pytest-collect,pytest-unit,pytest-full,import,sqlite-version,ruff-phase2,sentinel-scan}.txt
reports/evidence/p2/db/{schema.sql,table-list.txt,user-version.txt}
reports/evidence/p2/git/{status,log}.txt
```

No browser, API, SGLang, GPU, latency, accuracy, or judge-score result is claimed.

## Known limitations and deferred work

- Tests use synthetic fixtures only; no real 550/30 corpus count is claimed.
- Ingestion, parsing, chunking, source maps, retrieval, BM25/FTS5, evidence bundles, and retrieval traces are Phase 3.
- Real entailment scoring and SGLang integration are Phase 4 and remain blocked by the absence of a local GPU.
- `require_train_only(snapshot_id, family_ids)` has no actor parameter in the frozen contract. Callers must pass a snapshot ID already resolved within their tenant; Phase 3/6 should keep this helper behind tenant-scoped orchestration.
- Full-repository lint is not clean because of pre-existing Phase 1 findings listed above.
- `reports/phase-0.md` remains missing; P0 is recorded as implemented in the status file without a formal report.

## Next gate

Phase 3: ingestion, canonical source maps, ACL-first retrieval, deterministic evidence bundle and trace. It must consume the Phase 2 `authorize_chunk`/`authorized_chunks` API, never bypass live ACL, and must not introduce a retrieval path that can see a draft, stale, cross-tenant, or ungranted source.
