# P2 — corpus registry, versions, and ACL policy contract v1

OWNER: orchestrator
STATUS: frozen for Phase 2
SOURCE OF TRUTH: `IDEA.md` §10 split lock; `ARCHITECTURE.md` §§5–7, 10, 13–14; `WORKFLOWS.md` §§3–5, 13; `IMPLEMENTATION_PLAN.md` §5; this contract.

## Objective

Own document identity, immutability, temporal validity, authority, permissions, and frozen snapshot identity in one deterministic service before retrieval exists. Phase 2 must make it impossible for an unauthorized, draft, superseded, or expired source to be projected as current evidence, and must make corpus/split hashes reproducible.

## In scope

- SQLite schema and idempotent migration for principals, principal roles, documents, document families, versions, version text, version activation events, chunks, ACL grants, precedence rules, split assignments, snapshots, and audit events.
- Immutable document/version/chunk content; append-only activation events; derived version status.
- Explicit-version-pair precedence rules; no implicit authority ranking.
- Deny-by-default document-level ACLs; server-resolved principals; live ACL recheck on every content read.
- Family-level split assignment, four frozen split names, split-lock hash, duplicate-source leakage rejection, test/OOD train guard.
- Deterministic snapshot builder and verifier with content, manifest, and split-lock SHA-256 values.
- Unit and security tests for revoked ACL, cross-workspace IDs, superseded/draft/expired versions, active conflict, integrity mismatch, snapshot immutability, and split leakage.
- `.gitignore` protection for local databases and corpus data.

## Out of scope

- Ingestion, parsing, chunking algorithms, PDF geometry, source maps (Phase 3).
- BM25/FTS5/dense indexes, retrieval ranking, evidence-bundle composition, retrieval trace (Phase 3).
- SGLang, prompting, generation, entailment, repair, five-state resolution (Phase 4).
- HTTP routes, workbench UI, browser gates (Phase 5).
- CuratorKIT, AlignTune, AuditKIT, training, evaluation, feedback loop (Phases 6–8).
- Login/IdP/session storage; Phase 2 resolves an already-authenticated principal ID.
- Wildcards, role hierarchy, per-chunk ACL grants, cross-tenant sharing, admin content bypass, encryption at rest, deletion/retention automation.
- Real 550/30 corpus counts. Phase 2 tests use synthetic fixtures and record actual fixture counts only.
- Any change to frozen Phase 1 models, validators, error codes, or the Phase 1 contract.

## Spec conflict recorded

`AGENTS.md` §6 describes Phase 2 as including a deterministic evidence bundle with trace and permissions. `IMPLEMENTATION_PLAN.md` §5 gates Phase 2 only on corpus/ACL/version/snapshot, and §6 puts retrieval, bundle, trace, and permissions in Phase 3. This contract follows the narrower, stricter plan: Phase 2 owns the registry, ACL service, split lock, and snapshot primitive; Phase 3 consumes the authorization API to build bundles. This conflict is recorded in `reports/phase-2.md` rather than silently resolved.

## Frozen interfaces

### Package and persistence

- New package: `src/hallx/corpus/`.
- Runtime dependency: Python standard library `sqlite3` only. No SQLAlchemy, Alembic, or new dependency.
- Database file is local and untracked. Tests use `tmp_path`.
- `PRAGMA foreign_keys = ON` on every connection. No shared connection across threads.
- Schema version: `SCHEMA_VERSION = 1`; migration is idempotent and checksum-verified.
- Unknown future schema version fails closed with `SCHEMA_VERSION_UNSUPPORTED`.
- No in-place content mutation, no `INSERT OR REPLACE`, no `DELETE` of content, snapshots, or audit rows.

### Tables

All content tables are `STRICT`; identifiers are opaque text; dates are ISO `YYYY-MM-DD`; timestamps are UTC ISO-8601 text.

- `schema_migrations(version INTEGER PRIMARY KEY, name TEXT, checksum TEXT, applied_at TEXT)`
- `principals(principal_id TEXT PRIMARY KEY, tenant_id TEXT, display_name TEXT, created_at TEXT, disabled INTEGER)`
- `principal_roles(principal_id TEXT, role TEXT, granted_at TEXT, granted_by TEXT, PRIMARY KEY(principal_id, role))`
- `documents(tenant_id TEXT, doc_id TEXT, family_id TEXT, title TEXT, source_path TEXT, media_type TEXT, uploaded_by TEXT, created_at TEXT, source_sha256 TEXT, authority TEXT, licence TEXT NULL, PRIMARY KEY(tenant_id, doc_id))`
- `document_versions(tenant_id TEXT, version_id TEXT, doc_id TEXT, version_label TEXT, source_sha256 TEXT, content_sha256 TEXT, canonicalization_version TEXT, effective_from TEXT, effective_until TEXT NULL, supersedes_version_id TEXT NULL, precedence_rule_id TEXT NULL, created_at TEXT, created_by TEXT, PRIMARY KEY(tenant_id, version_id), UNIQUE(tenant_id, doc_id, version_label), UNIQUE(tenant_id, supersedes_version_id))`
- `version_texts(tenant_id TEXT, version_id TEXT, canonical_text TEXT, canonical_sha256 TEXT, PRIMARY KEY(tenant_id, version_id))`
- `version_activation_events(event_seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, version_id TEXT, event_type TEXT CHECK(event_type = 'ACTIVATED'), occurred_at TEXT, actor_principal_id TEXT, reason TEXT, UNIQUE(tenant_id, version_id))`
- `chunks(tenant_id TEXT, chunk_id TEXT, doc_id TEXT, version_id TEXT, chunk_index INTEGER, original_text TEXT, canonical_text TEXT, canonical_sha256 TEXT, canonicalization_version TEXT, page_start INTEGER NULL, page_end INTEGER NULL, is_adversarial INTEGER, created_at TEXT, PRIMARY KEY(tenant_id, chunk_id), UNIQUE(tenant_id, version_id, chunk_index))`
- `acl_grants(tenant_id TEXT, doc_id TEXT, role TEXT, granted_at TEXT, granted_by TEXT, revoked_at TEXT NULL, revoked_by TEXT NULL, PRIMARY KEY(tenant_id, doc_id, role))`
- `precedence_rules(tenant_id TEXT, rule_id TEXT, winner_version_id TEXT, loser_version_id TEXT, reason TEXT, created_at TEXT, created_by TEXT, PRIMARY KEY(tenant_id, rule_id), UNIQUE(tenant_id, winner_version_id, loser_version_id))`
- `split_assignments(tenant_id TEXT, family_id TEXT, split_name TEXT CHECK(split_name IN ('train','validation','test_indomain','test_ood_challenge')), assigned_at TEXT, assigned_by TEXT, locked_by_snapshot_id TEXT NULL, PRIMARY KEY(tenant_id, family_id))`
- `snapshots(tenant_id TEXT, snapshot_id TEXT, manifest_version TEXT, manifest_sha256 TEXT, content_sha256 TEXT, split_lock_sha256 TEXT, index_version TEXT, manifest_json TEXT, created_at TEXT, created_by TEXT, PRIMARY KEY(tenant_id, snapshot_id), UNIQUE(tenant_id, manifest_sha256))`
- `audit_events(event_seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, actor_principal_id TEXT NULL, action TEXT, resource_type TEXT, resource_id TEXT NULL, decision TEXT, reason_code TEXT, occurred_at TEXT, metadata_json TEXT)`

Immutability triggers reject `UPDATE`/`DELETE` on `documents`, `document_versions`, `version_texts`, `version_activation_events`, `chunks`, `precedence_rules`, `snapshots`, and `audit_events`. `acl_grants` changes by inserting or setting `revoked_at`; history is preserved in `audit_events`. `split_assignments` may change only while `locked_by_snapshot_id IS NULL`.

### Error namespace

New `CorpusErrorCode` and `CorpusError` in `hallx.corpus.errors`. Do not extend Phase 1 `ErrorCode`.

Frozen codes: `CORPUS_NOT_FOUND`, `CORPUS_ACL_DENIED`, `CORPUS_ROLE_REQUIRED`, `DUPLICATE_RESOURCE`, `VERSION_IMMUTABLE`, `VERSION_TRANSITION_INVALID`, `SUPERSESSION_INVALID`, `EFFECTIVE_WINDOW_INVALID`, `CHUNK_HASH_MISMATCH`, `CANONICALIZATION_MISMATCH`, `SNAPSHOT_NOT_FOUND`, `SNAPSHOT_IMMUTABLE`, `SNAPSHOT_HASH_MISMATCH`, `SNAPSHOT_INCOMPLETE`, `SPLIT_FAMILY_LEAKAGE`, `SPLIT_DUPLICATE_SOURCE`, `SPLIT_LOCKED`, `SPLIT_INVALID`, `PRECEDENCE_INVALID`, `CONFLICT_INVALID`, `SCHEMA_VERSION_UNSUPPORTED`, `MIGRATION_FAILED`, `CORPUS_INTEGRITY_ERROR`.

Messages are fixed strings. They must not contain titles, paths, source text, canonical text, quotes, page images, or ACL role lists. Phase 3 maps corpus denials to Phase 1 `ACL_DENIED`, `TENANT_MISMATCH`, `UNKNOWN_CHUNK`, or `SOURCE_NOT_ACTIVE` at the validation boundary.

### Principal and ACL policy

- `tenant_id` is the single workspace/isolation boundary. Do not add a second workspace hierarchy.
- `resolve_principal(principal_id) -> Principal` loads tenant and roles from the database on every request. Client-supplied tenant or roles are not authority.
- `bootstrap_admin(principal)` succeeds only when no principals exist and the principal has `corpus_admin`. All subsequent principal creation requires `corpus_admin`.
- Mutations (`register_document`, `add_version`, `activate_version`, `add_chunk`, `grant_acl`, `revoke_acl`, `assign_split`, `add_precedence_rule`, `build_snapshot`) require `corpus_admin` in the actor's roles and actor tenant equality.
- `corpus_admin` does **not** bypass document content ACLs. It may manage metadata and grants; it reads content only through an explicit document grant.
- ACL is document-level only. Effective roles are active `acl_grants` rows (`revoked_at IS NULL`). Zero grants means deny. There is no implicit uploader/owner grant.
- `grant_acl(actor, doc_id, roles)` rejects empty roles, duplicate roles, whitespace, `*`, `public`, and `everyone`; it revives a revoked row and audits the change.
- `revoke_acl(actor, doc_id, roles)` sets `revoked_at`; it does not delete the row. The next read is denied.
- Content reads are authorized live. Frozen snapshots and old bundles are historical evidence, never authorization sources. A revoked ACL cannot be bypassed by a forged or reused bundle.
- Public read methods return uniform `CORPUS_NOT_FOUND` for cross-tenant IDs, missing IDs, no document grant, non-fresh evidence, or a chunk outside the requested snapshot. This prevents an existence oracle. Internal `authorize_chunk` may report `ACL_DENIED`/`SOURCE_NOT_ACTIVE` for diagnostics and audit, without hydrating text.
- `list_documents` and `list_versions` return only authorized items and expose no hidden counts. Non-admin document records redact `acl_roles`; admin records may show them.
- No positive ACL decision, authorized chunk-ID set, restricted text, title, path, or role list is cached in Phase 2.

### Version lifecycle and status

- Version content (IDs, label, source hash, content hash, canonicalization version, effective dates, supersession link, precedence rule) is immutable once inserted.
- `add_version(..., activate=False)` creates a `DRAFT`; `activate=False` requires no activation event. `activate=True` inserts content and one `ACTIVATED` event in the same transaction. `activate_version` appends the same event to a `DRAFT` and is idempotent for an already activated version.
- Status is derived at `as_of`, never stored:
  1. no activation event -> `DRAFT`;
  2. an activated direct successor (`supersedes_version_id = version_id`) with `effective_from <= as_of` -> `SUPERSEDED`;
  3. `effective_until < as_of` -> `EXPIRED`;
  4. otherwise -> `ACTIVE`. A future activated version may be `ACTIVE` by status but is not fresh.
- Freshness matches Phase 1 exactly: status `ACTIVE`, `effective_from <= as_of`, and `effective_until is None or as_of <= effective_until`. Both date boundaries are inclusive.
- At most one fresh version per document may exist. `resolve_active_version` returns it or `None`; more than one is `CORPUS_INTEGRITY_ERROR`.
- Supersession is same-tenant, same-document, non-self, no fork (`UNIQUE(tenant_id, supersedes_version_id)`), and cannot target an already superseded version. The successor's `effective_from` must not precede the predecessor's `effective_from`.
- A non-superseding version must not overlap an existing version of the same document. A superseding version may overlap because derived status makes the predecessor non-fresh. The predecessor row is never rewritten.
- `activate_version` rejects a version whose effective window is invalid or whose activation would create two fresh versions.
- A DRAFT version is not visible to non-admin reads and is excluded from snapshots.

### Precedence and conflicts

- `authority` is descriptive metadata only. It never auto-resolves a conflict.
- A precedence rule is an explicit, immutable pair of version IDs: winner and loser, same tenant, distinct. `add_precedence_rule` validates both versions exist.
- `resolve_version_conflict(actor, version_a_id, version_b_id, as_of)` requires access to both documents. If either version is not fresh, return `NOT_A_CONFLICT`. With no applicable rule, return `UNRESOLVED`. One distinct winning version -> `RESOLVED`. Rules with conflicting winners -> `AMBIGUOUS`. Ambiguous and unresolved are both fail-closed.
- Phase 2 does not claim semantic conflict detection. It provides deterministic precedence resolution for a pair; Phase 3 identifies candidate pairs and emits `ConflictPair` only for unresolved/ambiguous pairs.

### Split lock

- The split unit is `family_id` (a family may contain multiple documents). A family is assigned to exactly one of `train`, `validation`, `test_indomain`, `test_ood_challenge`.
- Every document in a snapshot must have a family and a split assignment. A family in two splits is `SPLIT_FAMILY_LEAKAGE`; the schema primary key normally prevents it.
- The same `source_sha256` appearing in different families assigned to different splits is `SPLIT_DUPLICATE_SOURCE`.
- Split assignment is mutable only before the first snapshot locks it. After lock, reassignment is `SPLIT_LOCKED`.
- `require_train_only(snapshot_id, family_ids)` raises `SPLIT_FAMILY_LEAKAGE` if any requested family is not in `train`.
- Phase 2 proves source-family isolation only. Question-level, label-level, and failure-category leakage remain Phase 6/8 obligations.

### Snapshot identity

`build_snapshot(actor, index_version="none")` creates one immutable, idempotent snapshot in a single transaction. `snapshot_id = "snap-" + manifest_sha256`.

Canonical JSON is UTF-8, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, no floats. Domain-separated SHA-256 prefixes:

- `hallx.corpus.manifest.v1\n`
- `hallx.corpus.content.v1\n`
- `hallx.corpus.split.v1\n`

The manifest preimage is exactly:

```json
{
  "manifest_version": "hallx-corpus-manifest-v1",
  "tenant_id": "<tenant>",
  "canonicalization_version": "nfkc-ws-v1",
  "index_version": "<index_version>",
  "documents": {"<doc_id>": {"family_id": "<family>", "source_sha256": "<hex>"}},
  "versions": {"<version_id>": {"doc_id": "<doc>", "content_sha256": "<hex>", "effective_from": "YYYY-MM-DD", "effective_until": null, "supersedes_version_id": null, "precedence_rule_id": null}},
  "chunks": {"<chunk_id>": {"version_id": "<version>", "canonical_sha256": "<hex>"}},
  "splits": {"train": ["<family>"], "validation": [], "test_indomain": [], "test_ood_challenge": []}
}
```

- `content_sha256` hashes the canonical JSON of only `documents`, `versions`, and `chunks`.
- `split_lock_sha256` hashes the canonical JSON of only `splits`.
- `manifest_sha256` hashes the full manifest.
- `created_at`, `snapshot_id`, absolute paths, ACL, status, titles, and DB row order are excluded.
- `CorpusSnapshot` (Phase 1 model) is constructed from the manifest; no Phase 1 model change is made. A P2 `SnapshotRecord` wrapper carries `tenant_id`, `manifest_version`, `content_sha256`, and `created_by`.
- The snapshot is a closed set: `authorized_chunks(snapshot_id=...)` returns only chunk IDs present in the manifest. Versions/chunks added later are not included.
- `verify_snapshot` recomputes all three hashes from `manifest_json`, then checks referenced live document/version/chunk hashes and current locked split assignments. Missing or mismatched rows raise `SNAPSHOT_HASH_MISMATCH`.
- Snapshot ACL is not stored or used for authorization. Live ACL is always rechecked.

### Audit

- Every mutation and every content denial writes one append-only `audit_events` row in the same transaction where applicable.
- Audit metadata is an internal allow-list of IDs, roles, hashes, dates, split names, and reason codes. It never contains titles, paths, text, quotes, canonical text, or model output.
- Audit rows cannot be updated or deleted.

### Public API

```python
class CorpusRegistry:
    @classmethod
    def open(cls, path: str | Path, *, clock: Callable[[], datetime] | None = None) -> "CorpusRegistry": ...
    def close(self) -> None: ...

    def bootstrap_admin(self, principal: Principal) -> None: ...
    def create_principal(self, actor: Principal, principal: Principal) -> None: ...
    def resolve_principal(self, principal_id: str) -> Principal: ...
    def set_principal_roles(self, actor: Principal, principal_id: str, roles: tuple[str, ...]) -> None: ...

    def register_document(self, actor: Principal, *, doc_id: str, family_id: str, title: str,
                          source_path: str, media_type: str, uploaded_by: str,
                          source_sha256: str, authority: str, licence: str | None = None) -> DocumentRecord: ...
    def add_version(self, actor: Principal, *, doc_id: str, version_id: str, version_label: str,
                    source_sha256: str, canonical_text: str, effective_from: date,
                    effective_until: date | None = None, supersedes_version_id: str | None = None,
                    precedence_rule_id: str | None = None, activate: bool = False) -> VersionRecord: ...
    def activate_version(self, actor: Principal, version_id: str, *, reason: str = "approved") -> VersionRecord: ...
    def add_chunk(self, actor: Principal, *, chunk_id: str, doc_id: str, version_id: str,
                  chunk_index: int, original_text: str, page_start: int | None = None,
                  page_end: int | None = None, is_adversarial: bool = False) -> ChunkRecord: ...

    def grant_acl(self, actor: Principal, doc_id: str, roles: tuple[str, ...]) -> None: ...
    def revoke_acl(self, actor: Principal, doc_id: str, roles: tuple[str, ...]) -> None: ...

    def add_precedence_rule(self, actor: Principal, *, rule_id: str, winner_version_id: str,
                            loser_version_id: str, reason: str) -> None: ...
    def resolve_version_conflict(self, actor: Principal, version_a_id: str, version_b_id: str,
                                 *, as_of: date) -> ConflictResolution: ...

    def assign_split(self, actor: Principal, family_id: str, split_name: str) -> None: ...
    def require_train_only(self, snapshot_id: str, family_ids: tuple[str, ...]) -> None: ...

    def build_snapshot(self, actor: Principal, *, index_version: str = "none") -> SnapshotRecord: ...
    def get_snapshot(self, actor: Principal, snapshot_id: str) -> SnapshotRecord: ...
    def verify_snapshot(self, actor: Principal, snapshot_id: str) -> SnapshotRecord: ...

    def list_documents(self, actor: Principal) -> tuple[DocumentRecord, ...]: ...
    def get_document(self, actor: Principal, doc_id: str) -> DocumentRecord: ...
    def list_versions(self, actor: Principal, doc_id: str) -> tuple[VersionRecord, ...]: ...
    def get_version(self, actor: Principal, doc_id: str, version_id: str, *, as_of: date) -> VersionRecord: ...
    def get_version_text(self, actor: Principal, doc_id: str, version_id: str) -> str: ...
    def resolve_active_version(self, actor: Principal, doc_id: str, *, as_of: date) -> VersionRecord | None: ...

    def authorize_chunk(self, actor: Principal, chunk_id: str, *, as_of: date,
                        snapshot_id: str | None = None) -> AuthorizationDecision: ...
    def get_authorized_chunk(self, actor: Principal, chunk_id: str, *, as_of: date,
                             snapshot_id: str | None = None) -> EvidenceChunk: ...
    def authorized_chunks(self, actor: Principal, *, as_of: date,
                          snapshot_id: str | None = None) -> tuple[EvidenceChunk, ...]: ...
    def stale_chunks(self, actor: Principal, *, as_of: date,
                     snapshot_id: str | None = None) -> tuple[EvidenceChunk, ...]: ...
```

`DocumentRecord`, `VersionRecord`, `ChunkRecord`, `SnapshotRecord`, `ConflictResolution`, and `AuthorizationDecision` are P2 projection records. They do not replace or mutate Phase 1 models. `EvidenceChunk` is the only Phase 1 runtime view hydrated by P2, and only after authorization.

## Write paths

All Phase 2 write paths are orchestrator-owned; no parallel writer may touch a frozen Phase 1 file.

- `Project/src/hallx/corpus/**`
- `Project/tests/support_corpus.py`
- `Project/tests/unit/test_corpus_*.py`
- `Project/tests/security/__init__.py`
- `Project/tests/security/test_acl_corpus.py`
- `Project/reports/contracts/P2-corpus-and-acl.md`
- `Project/reports/phase-2.md`
- `Project/reports/evidence/p2/**`
- `Project/.gitignore` (DB/data ignore entries only)
- `Project/IMPLEMENTATION_STATUS.md`

Frozen and untouched: all `src/hallx/models.py`, `errors.py`, `canonical.py`, `source_map.py`, `validation/**`, P1 tests, P1 contract, specs.

## Acceptance

Run from `Project/` and save exact command, exit code, and output:

```powershell
uv sync --frozen
uv run python -c "import sys, sqlite3; print(sys.version); print(sqlite3.sqlite_version)"
uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"
uv run pytest tests/unit tests/security --collect-only -q -k "corpus or acl or version or snapshot"
uv run pytest tests/unit -q
uv run pytest -q
uv run python -c "from hallx.corpus import CorpusRegistry, migrate; print('import-ok')"
```

Pass criteria:

- Gate exit 0; it collects and passes every Phase 2 test module, not only Phase 1's `test_canonicalization_version_is_pinned`.
- Full suite green (35 Phase 1 tests plus Phase 2 tests); no Phase 1 edits.
- Two independent builds over identical logical inputs produce identical `manifest_sha256`, `content_sha256`, and `split_lock_sha256`; insertion order, database path, clock, and `snapshot_id` do not affect them.
- A content change changes `manifest_sha256`/`content_sha256` but not `split_lock_sha256`; a split/family change changes `split_lock_sha256`.
- Superseded, draft, future, and expired versions are never returned as fresh evidence.
- Revoked ACL, cross-workspace ID, guessed restricted chunk ID, and forged bundle ACL all deny without restricted text.
- Snapshot rows and content rows reject update/delete.
- No restricted sentinel text appears in errors, audit metadata, or evidence logs.
- No `.db`/`.sqlite3`/`data/` artifact is staged.

## Invariants and test IDs

- `test_corpus_migrations.py`: idempotent migration, checksum mismatch, unsupported version, foreign keys.
- `test_corpus_versions.py`: immutable content, draft/superseded/expired not active, inclusive boundaries, no fork, cross-document supersession rejected, no duplicate active version, activation idempotent.
- `test_corpus_conflicts.py`: unresolved active pair, explicit rule resolves, opposite rules ambiguous, authority alone does not resolve, stale pair is not a conflict.
- `test_corpus_splits.py`: family assigned once, family leakage rejected, duplicate source across splits rejected, lock prevents reassignment, train-only guard rejects test/OOD.
- `test_corpus_snapshot.py`: reproducible across insertion order, content vs split hash separation, snapshot closed set, immutable rows, tampered manifest/live hash detected, actual counts only.
- `test_corpus_audit.py`: mutation audit rows, append-only, no sentinel content.
- `tests/security/test_acl_corpus.py`: deny by default, revoked ACL after prior read, source-open recheck, cross-workspace not-found, guessed chunk ID not hydrated, admin no bypass, forged bundle ACL cannot override live ACL, no restricted text in errors/logs.

## Evidence

```text
Project/reports/evidence/p2/logs/{uv-sync,pytest-gate,pytest-gate-rerun,pytest-collect,pytest-unit,pytest-full,import,sqlite-version,sentinel-scan}.txt
Project/reports/evidence/p2/db/{schema.sql,table-list.txt,user-version.txt}
Project/reports/evidence/p2/git/{status,log}.txt
Project/reports/phase-2.md
```

No browser gate applies: Phase 2 is service-only. Do not claim a browser, API, SGLang, GPU, or performance result.

## Stop / blocked conditions

Stop and report **blocked**, do not guess, if:

- A frozen Phase 1 model, validator, error code, test, or contract must change.
- Snapshot hashes require volatile inputs or cannot be reproduced across processes/insertion order.
- ACL must live in the UI/session or rely on a client-supplied tenant/role.
- Admin content bypass, version mutation in place, snapshot deletion, or real restricted documents are proposed.
- The gate cannot collect Phase 2 tests or a new dependency/GPU/network is required.
- A semantic conflict or split-leakage rule cannot be represented without inventing data.

## Changes

v1 initial. Decisions: no Phase 1 schema bump (P2 wrapper records); document-level ACL only; append-only activation events with derived status; explicit version-pair precedence; content-only snapshot with separate split lock; live ACL recheck; uniform not-found for content reads.
