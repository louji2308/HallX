"""Corpus registry, ACL policy, version lifecycle, and snapshots."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize
from hallx.corpus.db import connect, migrate, transaction
from hallx.corpus.errors import CorpusError, CorpusErrorCode
from hallx.corpus.records import (
    AuthorizationDecision,
    ChunkRecord,
    ConflictResolution,
    DocumentRecord,
    SnapshotRecord,
    VersionRecord,
)
from hallx.corpus.snapshot import (
    MANIFEST_VERSION,
    canonical_json,
    compute_hashes,
    snapshot_id_for,
)
from hallx.models import CorpusSnapshot, DocumentStatus, EvidenceChunk, Principal

CORPUS_ADMIN_ROLE = "corpus_admin"
SPLIT_NAMES = ("train", "validation", "test_indomain", "test_ood_challenge")
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_ROLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
_RESERVED_ROLES = frozenset({"*", "public", "everyone"})
_AUDIT_METADATA_KEYS = frozenset(
    {
        "activated",
        "chunk_id_sha256",
        "content_sha256",
        "doc_id",
        "family_id",
        "manifest_sha256",
        "reason",
        "role",
        "roles",
        "rule_id",
        "split",
        "split_lock_sha256",
        "version_id",
    }
)


def _utc_now(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc_now(value).isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _invalid_manifest(message: str) -> CorpusError:
    return CorpusError(CorpusErrorCode.SNAPSHOT_HASH_MISMATCH, message)


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise _invalid_manifest("snapshot manifest is invalid")
    required = {
        "manifest_version",
        "tenant_id",
        "canonicalization_version",
        "index_version",
        "documents",
        "versions",
        "chunks",
        "splits",
    }
    if set(manifest) != required:
        raise _invalid_manifest("snapshot manifest keys are invalid")
    for key in ("manifest_version", "tenant_id", "canonicalization_version", "index_version"):
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise _invalid_manifest("snapshot manifest metadata is invalid")
    for key in ("documents", "versions", "chunks", "splits"):
        if not isinstance(manifest[key], dict):
            raise _invalid_manifest("snapshot manifest content is invalid")
    splits = manifest["splits"]
    if set(splits) != set(SPLIT_NAMES):
        raise _invalid_manifest("snapshot manifest splits are invalid")
    for families in splits.values():
        if not isinstance(families, list) or not all(isinstance(item, str) for item in families):
            raise _invalid_manifest("snapshot manifest splits are invalid")
    for doc_id, data in manifest["documents"].items():
        if (
            not isinstance(doc_id, str)
            or not isinstance(data, dict)
            or set(data) != {"family_id", "source_sha256"}
            or not isinstance(data["family_id"], str)
            or not isinstance(data["source_sha256"], str)
        ):
            raise _invalid_manifest("snapshot manifest documents are invalid")
    version_keys = {
        "doc_id",
        "content_sha256",
        "effective_from",
        "effective_until",
        "supersedes_version_id",
        "precedence_rule_id",
    }
    for version_id, data in manifest["versions"].items():
        if (
            not isinstance(version_id, str)
            or not isinstance(data, dict)
            or set(data) != version_keys
            or not isinstance(data["doc_id"], str)
            or not isinstance(data["content_sha256"], str)
            or not isinstance(data["effective_from"], str)
            or (data["effective_until"] is not None and not isinstance(data["effective_until"], str))
            or (
                data["supersedes_version_id"] is not None
                and not isinstance(data["supersedes_version_id"], str)
            )
            or (
                data["precedence_rule_id"] is not None
                and not isinstance(data["precedence_rule_id"], str)
            )
        ):
            raise _invalid_manifest("snapshot manifest versions are invalid")
    for chunk_id, data in manifest["chunks"].items():
        if (
            not isinstance(chunk_id, str)
            or not isinstance(data, dict)
            or set(data) != {"version_id", "canonical_sha256"}
            or not isinstance(data["version_id"], str)
            or not isinstance(data["canonical_sha256"], str)
        ):
            raise _invalid_manifest("snapshot manifest chunks are invalid")


def _transactional(method: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(method)
    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        with transaction(self._connection):
            return method(self, *args, **kwargs)

    return wrapper


class CorpusRegistry:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def open(
        cls,
        path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> CorpusRegistry:
        connection = connect(path)
        try:
            migrate(connection)
        except Exception:
            connection.close()
            raise
        return cls(connection, clock=clock)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def _now(self) -> datetime:
        return _utc_now(self._clock())

    def _today(self) -> date:
        return self._now().date()

    @staticmethod
    def _require_text(value: str, *, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, f"{name} is required")

    @staticmethod
    def _require_hex(value: str, *, name: str) -> None:
        if not isinstance(value, str) or _HEX_RE.fullmatch(value) is None:
            raise CorpusError(
                CorpusErrorCode.CORPUS_INTEGRITY_ERROR,
                f"{name} must be a lowercase SHA-256 hex digest",
            )

    @staticmethod
    def _validate_roles(roles: Iterable[str]) -> tuple[str, ...]:
        values = tuple(roles)
        if not values:
            raise CorpusError(CorpusErrorCode.CORPUS_ROLE_REQUIRED, "at least one role is required")
        if len(values) != len(set(values)):
            raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "roles must be unique")
        for role in values:
            if not isinstance(role, str) or _ROLE_RE.fullmatch(role) is None:
                raise CorpusError(CorpusErrorCode.CORPUS_ACL_DENIED, "role name is not valid")
            if role.lower() in _RESERVED_ROLES:
                raise CorpusError(CorpusErrorCode.CORPUS_ACL_DENIED, "wildcard roles are not allowed")
        return values

    @staticmethod
    def _validate_split(split_name: str) -> None:
        if split_name not in SPLIT_NAMES:
            raise CorpusError(CorpusErrorCode.SPLIT_INVALID, "split name is not recognized")

    def _resolve_actor(self, principal_id: str, *, not_found: bool = False) -> Principal:
        row = self._connection.execute(
            "SELECT principal_id, tenant_id, disabled FROM principals WHERE principal_id = ?",
            (principal_id,),
        ).fetchone()
        if row is None or bool(row["disabled"]):
            code = CorpusErrorCode.CORPUS_NOT_FOUND if not_found else CorpusErrorCode.CORPUS_ACL_DENIED
            raise CorpusError(code, "principal is not available")
        roles = tuple(
            role_row["role"]
            for role_row in self._connection.execute(
                "SELECT role FROM principal_roles WHERE principal_id = ? ORDER BY role",
                (principal_id,),
            )
        )
        if not roles:
            raise CorpusError(CorpusErrorCode.CORPUS_ACL_DENIED, "principal has no active roles")
        return Principal(principal_id=row["principal_id"], tenant_id=row["tenant_id"], roles=roles)

    def _resolve_admin(self, actor: Principal) -> Principal:
        resolved = self._resolve_actor(actor.principal_id)
        if CORPUS_ADMIN_ROLE not in resolved.roles:
            raise CorpusError(
                CorpusErrorCode.CORPUS_ROLE_REQUIRED,
                "corpus administrator role is required",
            )
        return resolved

    def _document_row(self, tenant_id: str, doc_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM documents WHERE tenant_id = ? AND doc_id = ?",
            (tenant_id, doc_id),
        ).fetchone()
        if row is None:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        return row

    def _version_row(self, tenant_id: str, version_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM document_versions WHERE tenant_id = ? AND version_id = ?",
            (tenant_id, version_id),
        ).fetchone()
        if row is None:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document version is not available")
        return row

    def _effective_roles(self, tenant_id: str, doc_id: str) -> tuple[str, ...]:
        return tuple(
            row["role"]
            for row in self._connection.execute(
                "SELECT role FROM acl_grants "
                "WHERE tenant_id = ? AND doc_id = ? AND revoked_at IS NULL "
                "ORDER BY role",
                (tenant_id, doc_id),
            )
        )

    @staticmethod
    def _can_read(actor: Principal, row: sqlite3.Row, roles: tuple[str, ...]) -> bool:
        return row["tenant_id"] == actor.tenant_id and bool(set(roles).intersection(actor.roles))

    def _require_content_document(
        self, actor: Principal, doc_id: str
    ) -> tuple[sqlite3.Row, tuple[str, ...]]:
        resolved = self._resolve_actor(actor.principal_id)
        row = self._document_row(resolved.tenant_id, doc_id)
        roles = self._effective_roles(resolved.tenant_id, doc_id)
        if not self._can_read(resolved, row, roles):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        return row, roles

    def _status_at(self, row: sqlite3.Row, as_of: date) -> DocumentStatus:
        activated = self._connection.execute(
            "SELECT 1 FROM version_activation_events WHERE tenant_id = ? AND version_id = ?",
            (row["tenant_id"], row["version_id"]),
        ).fetchone()
        if activated is None:
            return DocumentStatus.DRAFT
        successor = self._connection.execute(
            "SELECT 1 FROM document_versions v "
            "JOIN version_activation_events e "
            "ON e.tenant_id = v.tenant_id AND e.version_id = v.version_id "
            "WHERE v.tenant_id = ? AND v.supersedes_version_id = ? "
            "AND v.effective_from <= ? LIMIT 1",
            (row["tenant_id"], row["version_id"], as_of.isoformat()),
        ).fetchone()
        if successor is not None:
            return DocumentStatus.SUPERSEDED
        until = row["effective_until"]
        if until is not None and until < as_of.isoformat():
            return DocumentStatus.EXPIRED
        return DocumentStatus.ACTIVE

    @staticmethod
    def _is_fresh(row: sqlite3.Row, as_of: date, status: DocumentStatus) -> bool:
        if status is not DocumentStatus.ACTIVE:
            return False
        if row["effective_from"] > as_of.isoformat():
            return False
        until = row["effective_until"]
        return until is None or as_of.isoformat() <= until

    def _version_rows(self, tenant_id: str, doc_id: str) -> tuple[sqlite3.Row, ...]:
        return tuple(
            self._connection.execute(
                "SELECT * FROM document_versions WHERE tenant_id = ? AND doc_id = ? "
                "ORDER BY effective_from, version_id",
                (tenant_id, doc_id),
            )
        )

    def _fresh_versions(self, tenant_id: str, doc_id: str, as_of: date) -> tuple[sqlite3.Row, ...]:
        fresh = []
        for row in self._version_rows(tenant_id, doc_id):
            status = self._status_at(row, as_of)
            if self._is_fresh(row, as_of, status):
                fresh.append(row)
        if len(fresh) > 1:
            raise CorpusError(
                CorpusErrorCode.CORPUS_INTEGRITY_ERROR,
                "more than one fresh version exists for a document",
            )
        return tuple(fresh)

    def _assert_no_overlap(
        self,
        tenant_id: str,
        doc_id: str,
        effective_from: date,
        effective_until: date | None,
    ) -> None:
        new_end = effective_until or date.max
        for row in self._version_rows(tenant_id, doc_id):
            old_start = _parse_date(row["effective_from"])
            old_end = _parse_date(row["effective_until"]) if row["effective_until"] else date.max
            if effective_from <= old_end and old_start <= new_end:
                raise CorpusError(
                    CorpusErrorCode.EFFECTIVE_WINDOW_INVALID,
                    "version effective window overlaps an existing version",
                )

    def _assert_single_fresh(self, tenant_id: str, doc_id: str, as_of: date) -> None:
        self._fresh_versions(tenant_id, doc_id, as_of)

    def _audit(
        self,
        *,
        tenant_id: str,
        actor_principal_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        decision: str,
        reason_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = metadata or {}
        unknown = set(payload).difference(_AUDIT_METADATA_KEYS)
        if unknown:
            raise CorpusError(
                CorpusErrorCode.CORPUS_INTEGRITY_ERROR,
                "audit metadata contains a disallowed key",
            )
        self._connection.execute(
            "INSERT INTO audit_events("
            "tenant_id, actor_principal_id, action, resource_type, resource_id, "
            "decision, reason_code, occurred_at, metadata_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                actor_principal_id,
                action,
                resource_type,
                resource_id,
                decision,
                reason_code,
                _iso(self._now()),
                canonical_json(payload),
            ),
        )

    def bootstrap_admin(self, principal: Principal) -> None:
        roles = self._validate_roles(principal.roles)
        if CORPUS_ADMIN_ROLE not in roles:
            raise CorpusError(
                CorpusErrorCode.CORPUS_ROLE_REQUIRED,
                "bootstrap principal requires corpus_admin",
            )
        self._require_text(principal.principal_id, name="principal_id")
        self._require_text(principal.tenant_id, name="tenant_id")
        count = self._connection.execute("SELECT COUNT(*) AS count FROM principals").fetchone()
        if int(count["count"]) != 0:
            raise CorpusError(
                CorpusErrorCode.DUPLICATE_RESOURCE,
                "bootstrap is only available before any principal exists",
            )
        now = _iso(self._now())
        with transaction(self._connection):
            self._connection.execute(
                "INSERT INTO principals(principal_id, tenant_id, display_name, created_at, disabled) "
                "VALUES (?, ?, ?, ?, 0)",
                (principal.principal_id, principal.tenant_id, principal.principal_id, now),
            )
            for role in sorted(roles):
                self._connection.execute(
                    "INSERT INTO principal_roles(principal_id, role, granted_at, granted_by) "
                    "VALUES (?, ?, ?, ?)",
                    (principal.principal_id, role, now, principal.principal_id),
                )
            self._audit(
                tenant_id=principal.tenant_id,
                actor_principal_id=principal.principal_id,
                action="PRINCIPAL_CREATED",
                resource_type="PRINCIPAL",
                resource_id=principal.principal_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"roles": sorted(roles)},
            )

    def create_principal(self, actor: Principal, principal: Principal) -> None:
        admin = self._resolve_admin(actor)
        if principal.tenant_id != admin.tenant_id:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "tenant is not available")
        self._require_text(principal.principal_id, name="principal_id")
        roles = self._validate_roles(principal.roles)
        now = _iso(self._now())
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT 1 FROM principals WHERE principal_id = ?",
                (principal.principal_id,),
            ).fetchone()
            if existing is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "principal already exists")
            self._connection.execute(
                "INSERT INTO principals(principal_id, tenant_id, display_name, created_at, disabled) "
                "VALUES (?, ?, ?, ?, 0)",
                (principal.principal_id, admin.tenant_id, principal.principal_id, now),
            )
            for role in sorted(roles):
                self._connection.execute(
                    "INSERT INTO principal_roles(principal_id, role, granted_at, granted_by) "
                    "VALUES (?, ?, ?, ?)",
                    (principal.principal_id, role, now, admin.principal_id),
                )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="PRINCIPAL_CREATED",
                resource_type="PRINCIPAL",
                resource_id=principal.principal_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"roles": sorted(roles)},
            )

    def resolve_principal(self, principal_id: str) -> Principal:
        return self._resolve_actor(principal_id, not_found=True)

    def set_principal_roles(
        self, actor: Principal, principal_id: str, roles: tuple[str, ...]
    ) -> None:
        admin = self._resolve_admin(actor)
        values = self._validate_roles(roles)
        target = self._connection.execute(
            "SELECT principal_id, tenant_id FROM principals WHERE principal_id = ?",
            (principal_id,),
        ).fetchone()
        if target is None or target["tenant_id"] != admin.tenant_id:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "principal is not available")
        current = {
            row["role"]
            for row in self._connection.execute(
                "SELECT role FROM principal_roles WHERE principal_id = ?",
                (principal_id,),
            )
        }
        if CORPUS_ADMIN_ROLE in current and CORPUS_ADMIN_ROLE not in values:
            other_admins = self._connection.execute(
                "SELECT COUNT(*) AS count FROM principal_roles "
                "WHERE role = ? AND principal_id <> ?",
                (CORPUS_ADMIN_ROLE, principal_id),
            ).fetchone()
            if int(other_admins["count"]) == 0:
                raise CorpusError(
                    CorpusErrorCode.CORPUS_ROLE_REQUIRED,
                    "at least one corpus administrator is required",
                )
        now = _iso(self._now())
        with transaction(self._connection):
            for role in sorted(current.difference(values)):
                self._connection.execute(
                    "DELETE FROM principal_roles WHERE principal_id = ? AND role = ?",
                    (principal_id, role),
                )
            for role in sorted(set(values).difference(current)):
                self._connection.execute(
                    "INSERT INTO principal_roles(principal_id, role, granted_at, granted_by) "
                    "VALUES (?, ?, ?, ?)",
                    (principal_id, role, now, admin.principal_id),
                )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="PRINCIPAL_ROLES_CHANGED",
                resource_type="PRINCIPAL",
                resource_id=principal_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"roles": sorted(values)},
            )

    def register_document(
        self,
        actor: Principal,
        *,
        doc_id: str,
        family_id: str,
        title: str,
        source_path: str,
        media_type: str,
        uploaded_by: str,
        source_sha256: str,
        authority: str,
        licence: str | None = None,
    ) -> DocumentRecord:
        admin = self._resolve_admin(actor)
        for value, name in (
            (doc_id, "doc_id"),
            (family_id, "family_id"),
            (title, "title"),
            (source_path, "source_path"),
            (media_type, "media_type"),
            (uploaded_by, "uploaded_by"),
            (authority, "authority"),
        ):
            self._require_text(value, name=name)
        self._require_hex(source_sha256, name="source_sha256")
        now = _iso(self._now())
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT 1 FROM documents WHERE tenant_id = ? AND doc_id = ?",
                (admin.tenant_id, doc_id),
            ).fetchone()
            if existing is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "document already exists")
            self._connection.execute(
                "INSERT INTO documents("
                "tenant_id, doc_id, family_id, title, source_path, media_type, uploaded_by, "
                "created_at, source_sha256, authority, licence"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    admin.tenant_id,
                    doc_id,
                    family_id,
                    title,
                    source_path,
                    media_type,
                    uploaded_by,
                    now,
                    source_sha256,
                    authority,
                    licence,
                ),
            )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="DOCUMENT_REGISTERED",
                resource_type="DOCUMENT",
                resource_id=doc_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"family_id": family_id},
            )
        row = self._document_row(admin.tenant_id, doc_id)
        return self._document_record(row, ())

    def add_version(
        self,
        actor: Principal,
        *,
        doc_id: str,
        version_id: str,
        version_label: str,
        source_sha256: str,
        canonical_text: str,
        effective_from: date,
        effective_until: date | None = None,
        supersedes_version_id: str | None = None,
        precedence_rule_id: str | None = None,
        activate: bool = False,
    ) -> VersionRecord:
        admin = self._resolve_admin(actor)
        for value, name in (
            (doc_id, "doc_id"),
            (version_id, "version_id"),
            (version_label, "version_label"),
            (canonical_text, "canonical_text"),
        ):
            self._require_text(value, name=name)
        self._require_hex(source_sha256, name="source_sha256")
        if effective_until is not None and effective_until < effective_from:
            raise CorpusError(
                CorpusErrorCode.EFFECTIVE_WINDOW_INVALID,
                "effective_until must not precede effective_from",
            )
        if supersedes_version_id == version_id:
            raise CorpusError(CorpusErrorCode.SUPERSESSION_INVALID, "a version cannot supersede itself")
        canonical = canonicalize(canonical_text)
        if canonical.text != canonical_text:
            raise CorpusError(
                CorpusErrorCode.CANONICALIZATION_MISMATCH,
                "version text is not canonical",
            )
        content_sha256 = canonical.sha256
        now = self._now()
        tenant_id = admin.tenant_id
        doc_row = self._document_row(tenant_id, doc_id)
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT 1 FROM document_versions WHERE tenant_id = ? AND version_id = ?",
                (tenant_id, version_id),
            ).fetchone()
            if existing is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "version already exists")
            if supersedes_version_id is not None:
                predecessor = self._version_row(tenant_id, supersedes_version_id)
                if predecessor["doc_id"] != doc_row["doc_id"]:
                    raise CorpusError(
                        CorpusErrorCode.SUPERSESSION_INVALID,
                        "supersession must stay within one document",
                    )
                if _parse_date(effective_from.isoformat()) < _parse_date(predecessor["effective_from"]):
                    raise CorpusError(
                        CorpusErrorCode.SUPERSESSION_INVALID,
                        "successor cannot start before its predecessor",
                    )
                fork = self._connection.execute(
                    "SELECT 1 FROM document_versions WHERE tenant_id = ? AND supersedes_version_id = ?",
                    (tenant_id, supersedes_version_id),
                ).fetchone()
                if fork is not None:
                    raise CorpusError(
                        CorpusErrorCode.SUPERSESSION_INVALID,
                        "a version cannot have more than one successor",
                    )
            else:
                self._assert_no_overlap(tenant_id, doc_id, effective_from, effective_until)
            self._connection.execute(
                "INSERT INTO document_versions("
                "tenant_id, version_id, doc_id, version_label, source_sha256, content_sha256, "
                "canonicalization_version, effective_from, effective_until, supersedes_version_id, "
                "precedence_rule_id, created_at, created_by"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    version_id,
                    doc_id,
                    version_label,
                    source_sha256,
                    content_sha256,
                    CANONICALIZATION_VERSION,
                    effective_from.isoformat(),
                    effective_until.isoformat() if effective_until else None,
                    supersedes_version_id,
                    precedence_rule_id,
                    _iso(now),
                    admin.principal_id,
                ),
            )
            self._connection.execute(
                "INSERT INTO version_texts(tenant_id, version_id, canonical_text, canonical_sha256) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, version_id, canonical_text, content_sha256),
            )
            if activate:
                self._insert_activation(tenant_id, version_id, admin.principal_id, "created active")
                self._assert_single_fresh(tenant_id, doc_id, now.date())
            self._audit(
                tenant_id=tenant_id,
                actor_principal_id=admin.principal_id,
                action="VERSION_CREATED",
                resource_type="VERSION",
                resource_id=version_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={
                    "doc_id": doc_id,
                    "version_id": version_id,
                    "activated": activate,
                },
            )
        row = self._version_row(tenant_id, version_id)
        return self._version_record(row, self._status_at(row, now.date()))

    def _insert_activation(
        self, tenant_id: str, version_id: str, actor_principal_id: str, reason: str
    ) -> None:
        self._connection.execute(
            "INSERT INTO version_activation_events("
            "tenant_id, version_id, event_type, occurred_at, actor_principal_id, reason"
            ") VALUES (?, ?, 'ACTIVATED', ?, ?, ?)",
            (tenant_id, version_id, _iso(self._now()), actor_principal_id, reason),
        )

    def activate_version(
        self, actor: Principal, version_id: str, *, reason: str = "approved"
    ) -> VersionRecord:
        admin = self._resolve_admin(actor)
        self._require_text(reason, name="reason")
        row = self._version_row(admin.tenant_id, version_id)
        existing = self._connection.execute(
            "SELECT 1 FROM version_activation_events WHERE tenant_id = ? AND version_id = ?",
            (admin.tenant_id, version_id),
        ).fetchone()
        if existing is not None:
            return self._version_record(row, self._status_at(row, self._today()))
        with transaction(self._connection):
            self._insert_activation(admin.tenant_id, version_id, admin.principal_id, reason)
            self._assert_single_fresh(admin.tenant_id, row["doc_id"], self._today())
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="VERSION_ACTIVATED",
                resource_type="VERSION",
                resource_id=version_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"doc_id": row["doc_id"], "version_id": version_id},
            )
        updated = self._version_row(admin.tenant_id, version_id)
        return self._version_record(updated, self._status_at(updated, self._today()))

    def add_chunk(
        self,
        actor: Principal,
        *,
        chunk_id: str,
        doc_id: str,
        version_id: str,
        chunk_index: int,
        original_text: str,
        page_start: int | None = None,
        page_end: int | None = None,
        is_adversarial: bool = False,
    ) -> ChunkRecord:
        admin = self._resolve_admin(actor)
        for value, name in (
            (chunk_id, "chunk_id"),
            (doc_id, "doc_id"),
            (version_id, "version_id"),
            (original_text, "original_text"),
        ):
            self._require_text(value, name=name)
        if chunk_index < 0:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "chunk_index must be non-negative")
        if page_start is not None and page_start < 1:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "page_start must be positive")
        if page_end is not None and page_end < 1:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "page_end must be positive")
        if page_start is not None and page_end is not None and page_end < page_start:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "page_end precedes page_start")
        doc_row = self._document_row(admin.tenant_id, doc_id)
        version_row = self._version_row(admin.tenant_id, version_id)
        if version_row["doc_id"] != doc_row["doc_id"]:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "chunk version does not match document")
        canonical = canonicalize(original_text)
        if not canonical.text:
            raise CorpusError(CorpusErrorCode.CANONICALIZATION_MISMATCH, "chunk canonical text is empty")
        now = _iso(self._now())
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT 1 FROM chunks WHERE tenant_id = ? AND chunk_id = ?",
                (admin.tenant_id, chunk_id),
            ).fetchone()
            if existing is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "chunk already exists")
            index_row = self._connection.execute(
                "SELECT 1 FROM chunks WHERE tenant_id = ? AND version_id = ? AND chunk_index = ?",
                (admin.tenant_id, version_id, chunk_index),
            ).fetchone()
            if index_row is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "chunk index already exists")
            self._connection.execute(
                "INSERT INTO chunks("
                "tenant_id, chunk_id, doc_id, version_id, chunk_index, original_text, canonical_text, "
                "canonical_sha256, canonicalization_version, page_start, page_end, is_adversarial, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    admin.tenant_id,
                    chunk_id,
                    doc_id,
                    version_id,
                    chunk_index,
                    original_text,
                    canonical.text,
                    canonical.sha256,
                    CANONICALIZATION_VERSION,
                    page_start,
                    page_end,
                    1 if is_adversarial else 0,
                    now,
                ),
            )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="CHUNK_CREATED",
                resource_type="CHUNK",
                resource_id=chunk_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"doc_id": doc_id, "version_id": version_id},
            )
        row = self._connection.execute(
            "SELECT * FROM chunks WHERE tenant_id = ? AND chunk_id = ?",
            (admin.tenant_id, chunk_id),
        ).fetchone()
        return self._chunk_record(row)

    def grant_acl(self, actor: Principal, doc_id: str, roles: tuple[str, ...]) -> None:
        admin = self._resolve_admin(actor)
        values = self._validate_roles(roles)
        self._document_row(admin.tenant_id, doc_id)
        now = _iso(self._now())
        with transaction(self._connection):
            for role in sorted(values):
                existing = self._connection.execute(
                    "SELECT 1 FROM acl_grants WHERE tenant_id = ? AND doc_id = ? AND role = ?",
                    (admin.tenant_id, doc_id, role),
                ).fetchone()
                if existing is None:
                    self._connection.execute(
                        "INSERT INTO acl_grants("
                        "tenant_id, doc_id, role, granted_at, granted_by, revoked_at, revoked_by"
                        ") VALUES (?, ?, ?, ?, ?, NULL, NULL)",
                        (admin.tenant_id, doc_id, role, now, admin.principal_id),
                    )
                else:
                    self._connection.execute(
                        "UPDATE acl_grants SET granted_at = ?, granted_by = ?, "
                        "revoked_at = NULL, revoked_by = NULL "
                        "WHERE tenant_id = ? AND doc_id = ? AND role = ?",
                        (now, admin.principal_id, admin.tenant_id, doc_id, role),
                    )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="ACL_GRANTED",
                resource_type="DOCUMENT",
                resource_id=doc_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"roles": sorted(values)},
            )

    def revoke_acl(self, actor: Principal, doc_id: str, roles: tuple[str, ...]) -> None:
        admin = self._resolve_admin(actor)
        values = self._validate_roles(roles)
        self._document_row(admin.tenant_id, doc_id)
        now = _iso(self._now())
        with transaction(self._connection):
            for role in sorted(values):
                self._connection.execute(
                    "UPDATE acl_grants SET revoked_at = ?, revoked_by = ? "
                    "WHERE tenant_id = ? AND doc_id = ? AND role = ? AND revoked_at IS NULL",
                    (now, admin.principal_id, admin.tenant_id, doc_id, role),
                )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="ACL_REVOKED",
                resource_type="DOCUMENT",
                resource_id=doc_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"roles": sorted(values)},
            )

    def add_precedence_rule(
        self,
        actor: Principal,
        *,
        rule_id: str,
        winner_version_id: str,
        loser_version_id: str,
        reason: str,
    ) -> None:
        admin = self._resolve_admin(actor)
        self._require_text(rule_id, name="rule_id")
        self._require_text(reason, name="reason")
        if winner_version_id == loser_version_id:
            raise CorpusError(CorpusErrorCode.CONFLICT_INVALID, "precedence pair must be distinct")
        self._version_row(admin.tenant_id, winner_version_id)
        self._version_row(admin.tenant_id, loser_version_id)
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT 1 FROM precedence_rules WHERE tenant_id = ? AND rule_id = ?",
                (admin.tenant_id, rule_id),
            ).fetchone()
            if existing is not None:
                raise CorpusError(CorpusErrorCode.DUPLICATE_RESOURCE, "precedence rule already exists")
            self._connection.execute(
                "INSERT INTO precedence_rules("
                "tenant_id, rule_id, winner_version_id, loser_version_id, reason, created_at, created_by"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    admin.tenant_id,
                    rule_id,
                    winner_version_id,
                    loser_version_id,
                    reason,
                    _iso(self._now()),
                    admin.principal_id,
                ),
            )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="PRECEDENCE_RULE_CREATED",
                resource_type="PRECEDENCE_RULE",
                resource_id=rule_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"rule_id": rule_id},
            )

    def resolve_version_conflict(
        self,
        actor: Principal,
        version_a_id: str,
        version_b_id: str,
        *,
        as_of: date,
    ) -> ConflictResolution:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        if version_a_id == version_b_id:
            raise CorpusError(CorpusErrorCode.CONFLICT_INVALID, "conflict pair must be distinct")
        version_a = self._version_row(resolved.tenant_id, version_a_id)
        version_b = self._version_row(resolved.tenant_id, version_b_id)
        doc_a = self._document_row(resolved.tenant_id, version_a["doc_id"])
        doc_b = self._document_row(resolved.tenant_id, version_b["doc_id"])
        roles_a = self._effective_roles(resolved.tenant_id, doc_a["doc_id"])
        roles_b = self._effective_roles(resolved.tenant_id, doc_b["doc_id"])
        if not self._can_read(resolved, doc_a, roles_a) or not self._can_read(resolved, doc_b, roles_b):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "conflict sources are not available")
        status_a = self._status_at(version_a, as_of)
        status_b = self._status_at(version_b, as_of)
        if not self._is_fresh(version_a, as_of, status_a) or not self._is_fresh(
            version_b, as_of, status_b
        ):
            return ConflictResolution(
                status="NOT_A_CONFLICT",
                reason="at least one source is not currently fresh",
            )
        rules = tuple(
            self._connection.execute(
                "SELECT rule_id, winner_version_id FROM precedence_rules "
                "WHERE tenant_id = ? AND ("
                "(winner_version_id = ? AND loser_version_id = ?) OR "
                "(winner_version_id = ? AND loser_version_id = ?)"
                ") ORDER BY rule_id",
                (
                    resolved.tenant_id,
                    version_a_id,
                    version_b_id,
                    version_b_id,
                    version_a_id,
                ),
            )
        )
        if not rules:
            return ConflictResolution(status="UNRESOLVED", reason="no precedence rule applies")
        winners = {row["winner_version_id"] for row in rules}
        rule_ids = tuple(row["rule_id"] for row in rules)
        if len(winners) > 1:
            return ConflictResolution(
                status="AMBIGUOUS",
                rule_ids=rule_ids,
                reason="precedence rules disagree about the winner",
            )
        return ConflictResolution(
            status="RESOLVED",
            winner_version_id=next(iter(winners)),
            rule_ids=rule_ids,
            reason="an explicit precedence rule resolves the pair",
        )

    def assign_split(self, actor: Principal, family_id: str, split_name: str) -> None:
        admin = self._resolve_admin(actor)
        self._require_text(family_id, name="family_id")
        self._validate_split(split_name)
        existing = self._connection.execute(
            "SELECT * FROM split_assignments WHERE tenant_id = ? AND family_id = ?",
            (admin.tenant_id, family_id),
        ).fetchone()
        if existing is not None and existing["locked_by_snapshot_id"] is not None:
            if existing["split_name"] == split_name:
                return
            raise CorpusError(CorpusErrorCode.SPLIT_LOCKED, "split assignment is already locked")
        with transaction(self._connection):
            if existing is None:
                self._connection.execute(
                    "INSERT INTO split_assignments("
                    "tenant_id, family_id, split_name, assigned_at, assigned_by, locked_by_snapshot_id"
                    ") VALUES (?, ?, ?, ?, ?, NULL)",
                    (admin.tenant_id, family_id, split_name, _iso(self._now()), admin.principal_id),
                )
            else:
                self._connection.execute(
                    "UPDATE split_assignments SET split_name = ?, assigned_at = ?, assigned_by = ? "
                    "WHERE tenant_id = ? AND family_id = ?",
                    (split_name, _iso(self._now()), admin.principal_id, admin.tenant_id, family_id),
                )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="SPLIT_ASSIGNED",
                resource_type="FAMILY",
                resource_id=family_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={"family_id": family_id, "split": split_name},
            )

    def require_train_only(self, snapshot_id: str, family_ids: tuple[str, ...]) -> None:
        row = self._connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_NOT_FOUND, "snapshot is not available")
        manifest = self._parse_manifest(row["manifest_json"])
        assignment: dict[str, str] = {}
        for split_name, families in manifest["splits"].items():
            for family_id in families:
                assignment[family_id] = split_name
        for family_id in family_ids:
            split_name = assignment.get(family_id)
            if split_name is None:
                raise CorpusError(CorpusErrorCode.SPLIT_INVALID, "family is not in the snapshot")
            if split_name != "train":
                raise CorpusError(
                    CorpusErrorCode.SPLIT_FAMILY_LEAKAGE,
                    "family is not in the train split",
                )

    @_transactional
    def build_snapshot(
        self, actor: Principal, *, index_version: str = "none"
    ) -> SnapshotRecord:
        admin = self._resolve_admin(actor)
        self._require_text(index_version, name="index_version")
        documents = tuple(
            self._connection.execute(
                "SELECT * FROM documents WHERE tenant_id = ? ORDER BY doc_id",
                (admin.tenant_id,),
            )
        )
        if not documents:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_INCOMPLETE, "snapshot requires a document")
        versions = tuple(
            self._connection.execute(
                "SELECT v.* FROM document_versions v "
                "JOIN version_activation_events e "
                "ON e.tenant_id = v.tenant_id AND e.version_id = v.version_id "
                "WHERE v.tenant_id = ? ORDER BY v.version_id",
                (admin.tenant_id,),
            )
        )
        if not versions:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_INCOMPLETE, "snapshot requires an active version")
        versions_by_doc: dict[str, list[sqlite3.Row]] = {}
        for row in versions:
            versions_by_doc.setdefault(row["doc_id"], []).append(row)
        for doc in documents:
            if not versions_by_doc.get(doc["doc_id"]):
                raise CorpusError(
                    CorpusErrorCode.SNAPSHOT_INCOMPLETE,
                    "every document requires an activated version",
                )
        assignments = {
            row["family_id"]: row
            for row in self._connection.execute(
                "SELECT * FROM split_assignments WHERE tenant_id = ?",
                (admin.tenant_id,),
            )
        }
        for doc in documents:
            if doc["family_id"] not in assignments:
                raise CorpusError(CorpusErrorCode.SPLIT_INVALID, "document family has no split")
        family_sources: dict[str, set[str]] = {}
        family_split: dict[str, str] = {}
        for doc in documents:
            family_sources.setdefault(doc["family_id"], set()).add(doc["source_sha256"])
            family_split[doc["family_id"]] = assignments[doc["family_id"]]["split_name"]
        families = sorted(family_sources)
        for index, first in enumerate(families):
            for second in families[index + 1 :]:
                if family_split[first] == family_split[second]:
                    continue
                if family_sources[first].intersection(family_sources[second]):
                    raise CorpusError(
                        CorpusErrorCode.SPLIT_DUPLICATE_SOURCE,
                        "the same source appears in different splits",
                    )
        version_ids = {row["version_id"] for row in versions}
        chunks = tuple(
            row
            for row in self._connection.execute(
                "SELECT * FROM chunks WHERE tenant_id = ? ORDER BY chunk_id",
                (admin.tenant_id,),
            )
            if row["version_id"] in version_ids
        )
        splits: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}
        for family_id, row in sorted(assignments.items()):
            splits[row["split_name"]].append(family_id)
        for name in SPLIT_NAMES:
            splits[name] = sorted(splits[name])
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "tenant_id": admin.tenant_id,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "index_version": index_version,
            "documents": {
                row["doc_id"]: {
                    "family_id": row["family_id"],
                    "source_sha256": row["source_sha256"],
                }
                for row in documents
            },
            "versions": {
                row["version_id"]: {
                    "doc_id": row["doc_id"],
                    "content_sha256": row["content_sha256"],
                    "effective_from": row["effective_from"],
                    "effective_until": row["effective_until"],
                    "supersedes_version_id": row["supersedes_version_id"],
                    "precedence_rule_id": row["precedence_rule_id"],
                }
                for row in versions
            },
            "chunks": {
                row["chunk_id"]: {
                    "version_id": row["version_id"],
                    "canonical_sha256": row["canonical_sha256"],
                }
                for row in chunks
            },
            "splits": splits,
        }
        hashes = compute_hashes(manifest)
        snapshot_id = snapshot_id_for(hashes.manifest_sha256)
        manifest_json = canonical_json(manifest)
        with transaction(self._connection):
            existing = self._connection.execute(
                "SELECT * FROM snapshots WHERE tenant_id = ? AND manifest_sha256 = ?",
                (admin.tenant_id, hashes.manifest_sha256),
            ).fetchone()
            if existing is not None:
                return self._snapshot_record(existing)
            self._connection.execute(
                "INSERT INTO snapshots("
                "tenant_id, snapshot_id, manifest_version, manifest_sha256, content_sha256, "
                "split_lock_sha256, index_version, manifest_json, created_at, created_by"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    admin.tenant_id,
                    snapshot_id,
                    MANIFEST_VERSION,
                    hashes.manifest_sha256,
                    hashes.content_sha256,
                    hashes.split_lock_sha256,
                    index_version,
                    manifest_json,
                    _iso(self._now()),
                    admin.principal_id,
                ),
            )
            for family_id in families:
                self._connection.execute(
                    "UPDATE split_assignments SET locked_by_snapshot_id = ? "
                    "WHERE tenant_id = ? AND family_id = ? AND locked_by_snapshot_id IS NULL",
                    (snapshot_id, admin.tenant_id, family_id),
                )
            self._audit(
                tenant_id=admin.tenant_id,
                actor_principal_id=admin.principal_id,
                action="SNAPSHOT_CREATED",
                resource_type="SNAPSHOT",
                resource_id=snapshot_id,
                decision="ALLOW",
                reason_code="OK",
                metadata={
                    "manifest_sha256": hashes.manifest_sha256,
                    "content_sha256": hashes.content_sha256,
                    "split_lock_sha256": hashes.split_lock_sha256,
                },
            )
        row = self._connection.execute(
            "SELECT * FROM snapshots WHERE tenant_id = ? AND snapshot_id = ?",
            (admin.tenant_id, snapshot_id),
        ).fetchone()
        return self._snapshot_record(row)

    def get_snapshot(self, actor: Principal, snapshot_id: str) -> SnapshotRecord:
        admin = self._resolve_admin(actor)
        row = self._snapshot_row(admin.tenant_id, snapshot_id)
        if row is None:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_NOT_FOUND, "snapshot is not available")
        return self._snapshot_record(row)

    def verify_snapshot(self, actor: Principal, snapshot_id: str) -> SnapshotRecord:
        admin = self._resolve_admin(actor)
        row = self._snapshot_row(admin.tenant_id, snapshot_id)
        if row is None:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_NOT_FOUND, "snapshot is not available")
        manifest = self._parse_manifest(row["manifest_json"])
        if manifest.get("manifest_version") != MANIFEST_VERSION:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_HASH_MISMATCH, "snapshot manifest version is wrong")
        if manifest.get("tenant_id") != admin.tenant_id:
            raise CorpusError(CorpusErrorCode.SNAPSHOT_HASH_MISMATCH, "snapshot tenant does not match")
        hashes = compute_hashes(manifest)
        if (
            hashes.manifest_sha256 != row["manifest_sha256"]
            or hashes.content_sha256 != row["content_sha256"]
            or hashes.split_lock_sha256 != row["split_lock_sha256"]
        ):
            raise CorpusError(CorpusErrorCode.SNAPSHOT_HASH_MISMATCH, "snapshot hashes do not match")
        for doc_id, expected in manifest["documents"].items():
            live = self._connection.execute(
                "SELECT * FROM documents WHERE tenant_id = ? AND doc_id = ?",
                (admin.tenant_id, doc_id),
            ).fetchone()
            if (
                live is None
                or live["source_sha256"] != expected["source_sha256"]
                or live["family_id"] != expected["family_id"]
            ):
                raise CorpusError(
                    CorpusErrorCode.SNAPSHOT_HASH_MISMATCH,
                    "snapshot document does not match live content",
                )
        for version_id, expected in manifest["versions"].items():
            live = self._connection.execute(
                "SELECT * FROM document_versions WHERE tenant_id = ? AND version_id = ?",
                (admin.tenant_id, version_id),
            ).fetchone()
            text = self._connection.execute(
                "SELECT canonical_sha256 FROM version_texts WHERE tenant_id = ? AND version_id = ?",
                (admin.tenant_id, version_id),
            ).fetchone()
            if (
                live is None
                or live["content_sha256"] != expected["content_sha256"]
                or live["doc_id"] != expected["doc_id"]
                or text is None
                or text["canonical_sha256"] != expected["content_sha256"]
            ):
                raise CorpusError(
                    CorpusErrorCode.SNAPSHOT_HASH_MISMATCH,
                    "snapshot version does not match live content",
                )
        for chunk_id, expected in manifest["chunks"].items():
            live = self._connection.execute(
                "SELECT * FROM chunks WHERE tenant_id = ? AND chunk_id = ?",
                (admin.tenant_id, chunk_id),
            ).fetchone()
            if (
                live is None
                or live["canonical_sha256"] != expected["canonical_sha256"]
                or live["version_id"] != expected["version_id"]
            ):
                raise CorpusError(
                    CorpusErrorCode.SNAPSHOT_HASH_MISMATCH,
                    "snapshot chunk does not match live content",
                )
        for split_name, families in manifest["splits"].items():
            for family_id in families:
                live = self._connection.execute(
                    "SELECT split_name FROM split_assignments WHERE tenant_id = ? AND family_id = ?",
                    (admin.tenant_id, family_id),
                ).fetchone()
                if live is None or live["split_name"] != split_name:
                    raise CorpusError(
                        CorpusErrorCode.SNAPSHOT_HASH_MISMATCH,
                        "snapshot split does not match live assignments",
                    )
        return self._snapshot_record(row)

    def list_documents(self, actor: Principal) -> tuple[DocumentRecord, ...]:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        is_admin = CORPUS_ADMIN_ROLE in resolved.roles
        records: list[DocumentRecord] = []
        for row in self._connection.execute(
            "SELECT * FROM documents WHERE tenant_id = ? ORDER BY doc_id",
            (resolved.tenant_id,),
        ):
            roles = self._effective_roles(resolved.tenant_id, row["doc_id"])
            if not is_admin and not self._can_read(resolved, row, roles):
                continue
            records.append(self._document_record(row, roles if is_admin else ()))
        return tuple(records)

    def get_document(self, actor: Principal, doc_id: str) -> DocumentRecord:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        row = self._document_row(resolved.tenant_id, doc_id)
        roles = self._effective_roles(resolved.tenant_id, doc_id)
        if CORPUS_ADMIN_ROLE in resolved.roles:
            return self._document_record(row, roles)
        if not self._can_read(resolved, row, roles):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        return self._document_record(row, ())

    def list_versions(self, actor: Principal, doc_id: str) -> tuple[VersionRecord, ...]:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        doc = self._document_row(resolved.tenant_id, doc_id)
        roles = self._effective_roles(resolved.tenant_id, doc_id)
        is_admin = CORPUS_ADMIN_ROLE in resolved.roles
        if not is_admin and not self._can_read(resolved, doc, roles):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        today = self._today()
        records = []
        for row in self._version_rows(resolved.tenant_id, doc_id):
            status = self._status_at(row, today)
            if not is_admin and status is DocumentStatus.DRAFT:
                continue
            records.append(self._version_record(row, status))
        return tuple(records)

    def get_version(
        self, actor: Principal, doc_id: str, version_id: str, *, as_of: date
    ) -> VersionRecord:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        doc = self._document_row(resolved.tenant_id, doc_id)
        roles = self._effective_roles(resolved.tenant_id, doc_id)
        is_admin = CORPUS_ADMIN_ROLE in resolved.roles
        if not is_admin and not self._can_read(resolved, doc, roles):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        row = self._version_row(resolved.tenant_id, version_id)
        if row["doc_id"] != doc_id:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document version is not available")
        status = self._status_at(row, as_of)
        if not is_admin and status is DocumentStatus.DRAFT:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document version is not available")
        return self._version_record(row, status)

    def get_version_text(self, actor: Principal, doc_id: str, version_id: str) -> str:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        doc, _ = self._require_content_document(resolved, doc_id)
        row = self._version_row(resolved.tenant_id, version_id)
        if row["doc_id"] != doc["doc_id"]:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document version is not available")
        if (
            CORPUS_ADMIN_ROLE not in resolved.roles
            and self._status_at(row, self._today()) is DocumentStatus.DRAFT
        ):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document version is not available")
        text = self._connection.execute(
            "SELECT canonical_text FROM version_texts WHERE tenant_id = ? AND version_id = ?",
            (resolved.tenant_id, version_id),
        ).fetchone()
        if text is None:
            raise CorpusError(CorpusErrorCode.CORPUS_INTEGRITY_ERROR, "version text is missing")
        return text["canonical_text"]

    def resolve_active_version(
        self, actor: Principal, doc_id: str, *, as_of: date
    ) -> VersionRecord | None:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        doc = self._document_row(resolved.tenant_id, doc_id)
        roles = self._effective_roles(resolved.tenant_id, doc_id)
        if (
            CORPUS_ADMIN_ROLE not in resolved.roles
            and not self._can_read(resolved, doc, roles)
        ):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "document is not available")
        fresh = self._fresh_versions(resolved.tenant_id, doc_id, as_of)
        if not fresh:
            return None
        return self._version_record(fresh[0], DocumentStatus.ACTIVE)

    def authorize_chunk(
        self,
        actor: Principal,
        chunk_id: str,
        *,
        as_of: date,
        snapshot_id: str | None = None,
    ) -> AuthorizationDecision:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        chunk = self._connection.execute(
            "SELECT * FROM chunks WHERE tenant_id = ? AND chunk_id = ?",
            (resolved.tenant_id, chunk_id),
        ).fetchone()
        if chunk is None:
            self._audit(
                tenant_id=resolved.tenant_id,
                actor_principal_id=resolved.principal_id,
                action="SOURCE_OPEN_DENIED",
                resource_type="CHUNK",
                resource_id=None,
                decision="DENY",
                reason_code=CorpusErrorCode.CORPUS_NOT_FOUND.value,
                metadata={"chunk_id_sha256": _hash_text(chunk_id)},
            )
            return AuthorizationDecision(allowed=False, reason_code="NOT_FOUND")
        doc = self._document_row(resolved.tenant_id, chunk["doc_id"])
        roles = self._effective_roles(resolved.tenant_id, chunk["doc_id"])
        if not self._can_read(resolved, doc, roles):
            self._audit(
                tenant_id=resolved.tenant_id,
                actor_principal_id=resolved.principal_id,
                action="SOURCE_OPEN_DENIED",
                resource_type="CHUNK",
                resource_id=chunk_id,
                decision="DENY",
                reason_code=CorpusErrorCode.CORPUS_ACL_DENIED.value,
            )
            return AuthorizationDecision(allowed=False, reason_code="ACL_DENIED")
        version = self._version_row(resolved.tenant_id, chunk["version_id"])
        status = self._status_at(version, as_of)
        if not self._is_fresh(version, as_of, status):
            self._audit(
                tenant_id=resolved.tenant_id,
                actor_principal_id=resolved.principal_id,
                action="SOURCE_OPEN_DENIED",
                resource_type="CHUNK",
                resource_id=chunk_id,
                decision="DENY",
                reason_code="SOURCE_NOT_ACTIVE",
            )
            return AuthorizationDecision(allowed=False, reason_code="NOT_FRESH")
        if snapshot_id is not None:
            snapshot = self._snapshot_row(resolved.tenant_id, snapshot_id)
            if snapshot is None:
                self._audit(
                    tenant_id=resolved.tenant_id,
                    actor_principal_id=resolved.principal_id,
                    action="SOURCE_OPEN_DENIED",
                    resource_type="CHUNK",
                    resource_id=None,
                    decision="DENY",
                    reason_code=CorpusErrorCode.CORPUS_NOT_FOUND.value,
                    metadata={"chunk_id_sha256": _hash_text(chunk_id)},
                )
                return AuthorizationDecision(allowed=False, reason_code="NOT_FOUND")
            manifest = self._parse_manifest(snapshot["manifest_json"])
            if chunk_id not in manifest["chunks"]:
                self._audit(
                    tenant_id=resolved.tenant_id,
                    actor_principal_id=resolved.principal_id,
                    action="SOURCE_OPEN_DENIED",
                    resource_type="CHUNK",
                    resource_id=chunk_id,
                    decision="DENY",
                    reason_code="NOT_IN_SNAPSHOT",
                )
                return AuthorizationDecision(allowed=False, reason_code="NOT_IN_SNAPSHOT")
        return AuthorizationDecision(allowed=True, reason_code="OK")

    def get_authorized_chunk(
        self,
        actor: Principal,
        chunk_id: str,
        *,
        as_of: date,
        snapshot_id: str | None = None,
    ) -> EvidenceChunk:
        decision = self.authorize_chunk(actor, chunk_id, as_of=as_of, snapshot_id=snapshot_id)
        if not decision.allowed:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "chunk is not available")
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        chunk = self._connection.execute(
            "SELECT * FROM chunks WHERE tenant_id = ? AND chunk_id = ?",
            (resolved.tenant_id, chunk_id),
        ).fetchone()
        doc = self._document_row(resolved.tenant_id, chunk["doc_id"])
        version = self._version_row(resolved.tenant_id, chunk["version_id"])
        roles = self._effective_roles(resolved.tenant_id, chunk["doc_id"])
        if not self._can_read(resolved, doc, roles):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "chunk is not available")
        status = self._status_at(version, as_of)
        if not self._is_fresh(version, as_of, status):
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "chunk is not available")
        if snapshot_id is not None:
            snapshot = self._snapshot_row(resolved.tenant_id, snapshot_id)
            if snapshot is None:
                raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "chunk is not available")
            if chunk_id not in self._parse_manifest(snapshot["manifest_json"])["chunks"]:
                raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "chunk is not available")
        return self._evidence_chunk(chunk, version, doc, roles, status)

    def authorized_chunks(
        self,
        actor: Principal,
        *,
        as_of: date,
        snapshot_id: str | None = None,
    ) -> tuple[EvidenceChunk, ...]:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        allowed_chunks = self._snapshot_chunk_ids(resolved.tenant_id, snapshot_id)
        records: list[EvidenceChunk] = []
        for doc in self._content_document_rows(resolved):
            roles = self._effective_roles(resolved.tenant_id, doc["doc_id"])
            for version in self._fresh_versions(resolved.tenant_id, doc["doc_id"], as_of):
                for chunk in self._chunks_for_version(resolved.tenant_id, version["version_id"]):
                    if allowed_chunks is not None and chunk["chunk_id"] not in allowed_chunks:
                        continue
                    records.append(
                        self._evidence_chunk(chunk, version, doc, roles, DocumentStatus.ACTIVE)
                    )
        records.sort(key=lambda item: item.chunk_id)
        return tuple(records)

    def stale_chunks(
        self,
        actor: Principal,
        *,
        as_of: date,
        snapshot_id: str | None = None,
    ) -> tuple[EvidenceChunk, ...]:
        resolved = self._resolve_actor(actor.principal_id, not_found=True)
        allowed_chunks = self._snapshot_chunk_ids(resolved.tenant_id, snapshot_id)
        records: list[EvidenceChunk] = []
        for doc in self._content_document_rows(resolved):
            roles = self._effective_roles(resolved.tenant_id, doc["doc_id"])
            for version in self._version_rows(resolved.tenant_id, doc["doc_id"]):
                status = self._status_at(version, as_of)
                if status not in (DocumentStatus.SUPERSEDED, DocumentStatus.EXPIRED):
                    continue
                for chunk in self._chunks_for_version(resolved.tenant_id, version["version_id"]):
                    if allowed_chunks is not None and chunk["chunk_id"] not in allowed_chunks:
                        continue
                    records.append(self._evidence_chunk(chunk, version, doc, roles, status))
        records.sort(key=lambda item: item.chunk_id)
        return tuple(records)

    def _content_document_rows(self, actor: Principal) -> tuple[sqlite3.Row, ...]:
        return tuple(
            row
            for row in self._connection.execute(
                "SELECT * FROM documents WHERE tenant_id = ? ORDER BY doc_id",
                (actor.tenant_id,),
            )
            if self._can_read(
                actor,
                row,
                self._effective_roles(actor.tenant_id, row["doc_id"]),
            )
        )

    def _chunks_for_version(self, tenant_id: str, version_id: str) -> tuple[sqlite3.Row, ...]:
        return tuple(
            self._connection.execute(
                "SELECT * FROM chunks WHERE tenant_id = ? AND version_id = ? ORDER BY chunk_id",
                (tenant_id, version_id),
            )
        )

    def _snapshot_row(self, tenant_id: str, snapshot_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM snapshots WHERE tenant_id = ? AND snapshot_id = ?",
            (tenant_id, snapshot_id),
        ).fetchone()

    def _snapshot_chunk_ids(
        self, tenant_id: str, snapshot_id: str | None
    ) -> set[str] | None:
        if snapshot_id is None:
            return None
        row = self._snapshot_row(tenant_id, snapshot_id)
        if row is None:
            raise CorpusError(CorpusErrorCode.CORPUS_NOT_FOUND, "snapshot is not available")
        manifest = self._parse_manifest(row["manifest_json"])
        return set(manifest["chunks"])

    @staticmethod
    def _parse_manifest(value: str) -> dict[str, Any]:
        try:
            manifest = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise CorpusError(
                CorpusErrorCode.SNAPSHOT_HASH_MISMATCH,
                "snapshot manifest is not valid JSON",
            ) from exc
        _validate_manifest(manifest)
        return manifest

    def _evidence_chunk(
        self,
        chunk: sqlite3.Row,
        version: sqlite3.Row,
        doc: sqlite3.Row,
        roles: tuple[str, ...],
        status: DocumentStatus,
    ) -> EvidenceChunk:
        canonical = canonicalize(chunk["original_text"])
        if canonical.text != chunk["canonical_text"]:
            raise CorpusError(
                CorpusErrorCode.CANONICALIZATION_MISMATCH,
                "chunk canonical text does not match its source",
            )
        if canonical.sha256 != chunk["canonical_sha256"]:
            raise CorpusError(
                CorpusErrorCode.CHUNK_HASH_MISMATCH,
                "chunk canonical hash does not match its text",
            )
        try:
            return EvidenceChunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                version_id=chunk["version_id"],
                version_label=version["version_label"],
                tenant_id=chunk["tenant_id"],
                status=status,
                effective_from=_parse_date(version["effective_from"]),
                effective_until=(
                    _parse_date(version["effective_until"])
                    if version["effective_until"] is not None
                    else None
                ),
                authority=doc["authority"],
                acl_roles=roles,
                original_text=chunk["original_text"],
                canonical_text=chunk["canonical_text"],
                canonical_sha256=chunk["canonical_sha256"],
                canonicalization_version=chunk["canonicalization_version"],
                source_sha256=version["source_sha256"],
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                precedence_rule_id=version["precedence_rule_id"],
                is_adversarial=bool(chunk["is_adversarial"]),
            )
        except ValueError as exc:
            raise CorpusError(
                CorpusErrorCode.CORPUS_INTEGRITY_ERROR,
                "stored chunk does not satisfy the evidence model",
            ) from exc

    def _document_record(self, row: sqlite3.Row, roles: tuple[str, ...]) -> DocumentRecord:
        return DocumentRecord(
            tenant_id=row["tenant_id"],
            doc_id=row["doc_id"],
            family_id=row["family_id"],
            title=row["title"],
            source_path=row["source_path"],
            media_type=row["media_type"],
            uploaded_by=row["uploaded_by"],
            created_at=_parse_dt(row["created_at"]),
            source_sha256=row["source_sha256"],
            authority=row["authority"],
            licence=row["licence"],
            acl_roles=roles,
        )

    def _version_record(self, row: sqlite3.Row, status: DocumentStatus) -> VersionRecord:
        return VersionRecord(
            tenant_id=row["tenant_id"],
            doc_id=row["doc_id"],
            version_id=row["version_id"],
            version_label=row["version_label"],
            source_sha256=row["source_sha256"],
            content_sha256=row["content_sha256"],
            canonicalization_version=row["canonicalization_version"],
            effective_from=_parse_date(row["effective_from"]),
            effective_until=(
                _parse_date(row["effective_until"])
                if row["effective_until"] is not None
                else None
            ),
            supersedes_version_id=row["supersedes_version_id"],
            precedence_rule_id=row["precedence_rule_id"],
            created_at=_parse_dt(row["created_at"]),
            created_by=row["created_by"],
            status=status,
        )

    def _chunk_record(self, row: sqlite3.Row) -> ChunkRecord:
        return ChunkRecord(
            tenant_id=row["tenant_id"],
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            version_id=row["version_id"],
            chunk_index=row["chunk_index"],
            original_text=row["original_text"],
            canonical_text=row["canonical_text"],
            canonical_sha256=row["canonical_sha256"],
            canonicalization_version=row["canonicalization_version"],
            page_start=row["page_start"],
            page_end=row["page_end"],
            is_adversarial=bool(row["is_adversarial"]),
            created_at=_parse_dt(row["created_at"]),
        )

    def _snapshot_record(self, row: sqlite3.Row) -> SnapshotRecord:
        manifest = self._parse_manifest(row["manifest_json"])
        document_hashes = {
            doc_id: data["source_sha256"] for doc_id, data in manifest["documents"].items()
        }
        version_hashes = {
            version_id: data["content_sha256"]
            for version_id, data in manifest["versions"].items()
        }
        chunk_hashes = {
            chunk_id: data["canonical_sha256"]
            for chunk_id, data in manifest["chunks"].items()
        }
        split_membership = {
            split_name: tuple(families)
            for split_name, families in manifest["splits"].items()
        }
        snapshot = CorpusSnapshot(
            snapshot_id=row["snapshot_id"],
            manifest_sha256=row["manifest_sha256"],
            document_hashes=document_hashes,
            version_hashes=version_hashes,
            chunk_hashes=chunk_hashes,
            split_membership=split_membership,
            split_lock_sha256=row["split_lock_sha256"],
            index_version=row["index_version"],
            created_at=_parse_dt(row["created_at"]),
        )
        return SnapshotRecord(
            tenant_id=row["tenant_id"],
            manifest_version=manifest["manifest_version"],
            content_sha256=row["content_sha256"],
            created_by=row["created_by"],
            snapshot=snapshot,
        )
