"""Shared builders for Phase 2 corpus tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from hallx.canonical import canonicalize
from hallx.corpus import CorpusRegistry, transaction
from hallx.models import Principal

TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"
AS_OF = date(2026, 10, 24)
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
SENTINEL = "RESTRICTED-SENTINEL-DO-NOT-LEAK"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def open_registry(
    tmp_path: Path,
    *,
    now: datetime = NOW,
    name: str = "corpus.db",
) -> CorpusRegistry:
    return CorpusRegistry.open(tmp_path / name, clock=lambda: now)


@pytest.fixture
def registry_fixture(tmp_path: Path):
    instance = open_registry(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def make_admin(registry: CorpusRegistry, principal_id: str = "admin-1") -> Principal:
    principal = Principal(
        principal_id=principal_id,
        tenant_id=TENANT,
        roles=("corpus_admin",),
    )
    registry.bootstrap_admin(principal)
    return principal


def make_user(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    principal_id: str = "user-1",
    roles: tuple[str, ...] = ("analyst",),
) -> Principal:
    registry.create_principal(
        admin,
        Principal(principal_id=principal_id, tenant_id=admin.tenant_id, roles=roles),
    )
    return Principal(principal_id=principal_id, tenant_id=admin.tenant_id, roles=roles)


def insert_foreign_principal(
    registry: CorpusRegistry,
    *,
    principal_id: str,
    tenant_id: str,
    roles: tuple[str, ...] = ("analyst",),
) -> None:
    granted_at = NOW.isoformat()
    with transaction(registry.connection):
        registry.connection.execute(
            "INSERT INTO principals(principal_id, tenant_id, display_name, created_at, disabled) "
            "VALUES (?, ?, ?, ?, 0)",
            (principal_id, tenant_id, principal_id, granted_at),
        )
        for role in roles:
            registry.connection.execute(
                "INSERT INTO principal_roles(principal_id, role, granted_at, granted_by) "
                "VALUES (?, ?, ?, ?)",
                (principal_id, role, granted_at, principal_id),
            )


def register_document(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    doc_id: str = "doc-1",
    family_id: str = "family-1",
    source_sha256: str | None = None,
    title: str = "Retention Policy",
    source_path: str = "corpus/retention.txt",
    media_type: str = "text/plain",
    authority: str = "policy",
    licence: str | None = "internal",
):
    return registry.register_document(
        admin,
        doc_id=doc_id,
        family_id=family_id,
        title=title,
        source_path=source_path,
        media_type=media_type,
        uploaded_by=admin.principal_id,
        source_sha256=source_sha256 or sha(f"source:{doc_id}"),
        authority=authority,
        licence=licence,
    )


def add_version(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    doc_id: str = "doc-1",
    version_id: str = "version-1",
    text: str = "The retention period is 30 days.",
    version_label: str | None = None,
    effective_from: date = date(2026, 1, 1),
    effective_until: date | None = None,
    supersedes_version_id: str | None = None,
    activate: bool = True,
):
    return registry.add_version(
        admin,
        doc_id=doc_id,
        version_id=version_id,
        version_label=version_label or version_id,
        source_sha256=sha(f"version-source:{version_id}"),
        canonical_text=canonicalize(text).text,
        effective_from=effective_from,
        effective_until=effective_until,
        supersedes_version_id=supersedes_version_id,
        activate=activate,
    )


def add_chunk(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    chunk_id: str = "chunk-1",
    doc_id: str = "doc-1",
    version_id: str = "version-1",
    chunk_index: int = 0,
    text: str = "The retention period is 30 days.",
    page_start: int | None = 1,
    page_end: int | None = 1,
    is_adversarial: bool = False,
):
    return registry.add_chunk(
        admin,
        chunk_id=chunk_id,
        doc_id=doc_id,
        version_id=version_id,
        chunk_index=chunk_index,
        original_text=text,
        page_start=page_start,
        page_end=page_end,
        is_adversarial=is_adversarial,
    )


def grant(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    doc_id: str = "doc-1",
    roles: tuple[str, ...] = ("analyst",),
) -> None:
    registry.grant_acl(admin, doc_id, roles)


def seed_chunk(
    registry: CorpusRegistry,
    admin: Principal,
    *,
    doc_id: str = "doc-1",
    family_id: str = "family-1",
    version_id: str = "version-1",
    chunk_id: str = "chunk-1",
    text: str = "The retention period is 30 days.",
    source_sha256: str | None = None,
    authority: str = "policy",
    effective_from: date = date(2026, 1, 1),
    effective_until: date | None = None,
):
    document = register_document(
        registry,
        admin,
        doc_id=doc_id,
        family_id=family_id,
        source_sha256=source_sha256,
        authority=authority,
    )
    version = add_version(
        registry,
        admin,
        doc_id=doc_id,
        version_id=version_id,
        text=text,
        effective_from=effective_from,
        effective_until=effective_until,
    )
    chunk = add_chunk(
        registry,
        admin,
        doc_id=doc_id,
        version_id=version_id,
        chunk_id=chunk_id,
        text=text,
    )
    return document, version, chunk


def audit_rows(registry: CorpusRegistry):
    return tuple(
        registry.connection.execute("SELECT * FROM audit_events ORDER BY event_seq")
    )
