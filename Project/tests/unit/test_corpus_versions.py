import sqlite3
from datetime import date

import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from hallx.models import DocumentStatus
from tests.support_corpus import (
    AS_OF,
    add_chunk,
    add_version,
    grant,
    make_admin,
    make_user,
    register_document,
    registry_fixture,
    seed_chunk,
    sha,
)

registry = registry_fixture


def test_draft_is_not_active_or_visible_to_non_admin(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    register_document(registry, admin)
    grant(registry, admin)

    draft = add_version(registry, admin, activate=False)

    assert draft.status is DocumentStatus.DRAFT
    assert registry.get_version(admin, "doc-1", "version-1", as_of=AS_OF).status is DocumentStatus.DRAFT
    assert registry.resolve_active_version(admin, "doc-1", as_of=AS_OF) is None
    with pytest.raises(CorpusError) as raised:
        registry.get_version(user, "doc-1", "version-1", as_of=AS_OF)
    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
    assert registry.list_versions(user, "doc-1") == ()


def test_active_boundaries_are_inclusive_and_expiry_is_enforced(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(
        registry,
        admin,
        effective_from=AS_OF,
        effective_until=AS_OF,
        activate=True,
    )

    active = registry.resolve_active_version(admin, "doc-1", as_of=AS_OF)
    assert active is not None
    assert active.status is DocumentStatus.ACTIVE
    assert registry.resolve_active_version(admin, "doc-1", as_of=date(2026, 10, 25)) is None
    assert (
        registry.get_version(admin, "doc-1", "version-1", as_of=date(2026, 10, 25)).status
        is DocumentStatus.EXPIRED
    )


def test_supersession_derives_status_without_mutating_predecessor(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(registry, admin, effective_from=date(2026, 1, 1), activate=True)
    add_version(
        registry,
        admin,
        version_id="version-2",
        text="The retention period is 60 days.",
        effective_from=date(2026, 2, 1),
        supersedes_version_id="version-1",
        activate=True,
    )

    predecessor = registry.get_version(admin, "doc-1", "version-1", as_of=AS_OF)
    successor = registry.get_version(admin, "doc-1", "version-2", as_of=AS_OF)
    active = registry.resolve_active_version(admin, "doc-1", as_of=AS_OF)
    assert predecessor.status is DocumentStatus.SUPERSEDED
    assert successor.status is DocumentStatus.ACTIVE
    assert active is not None and active.version_id == "version-2"
    assert registry.get_version(admin, "doc-1", "version-1", as_of=date(2026, 1, 15)).status is DocumentStatus.ACTIVE


def test_future_activated_version_is_not_fresh(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(
        registry,
        admin,
        effective_from=date(2026, 11, 1),
        activate=True,
    )

    record = registry.get_version(admin, "doc-1", "version-1", as_of=AS_OF)
    assert record.status is DocumentStatus.ACTIVE
    assert registry.resolve_active_version(admin, "doc-1", as_of=AS_OF) is None


def test_supersession_rejects_fork_and_cross_document_target(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1")
    register_document(registry, admin, doc_id="doc-2", family_id="family-2")
    add_version(registry, admin, doc_id="doc-1", version_id="version-1")
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-2",
        effective_from=date(2026, 2, 1),
        supersedes_version_id="version-1",
    )

    with pytest.raises(CorpusError) as fork:
        add_version(
            registry,
            admin,
            doc_id="doc-1",
            version_id="version-3",
            effective_from=date(2026, 3, 1),
            supersedes_version_id="version-1",
        )
    assert fork.value.code is CorpusErrorCode.SUPERSESSION_INVALID

    with pytest.raises(CorpusError) as cross_document:
        add_version(
            registry,
            admin,
            doc_id="doc-2",
            version_id="version-4",
            effective_from=date(2026, 3, 1),
            supersedes_version_id="version-1",
        )
    assert cross_document.value.code is CorpusErrorCode.SUPERSESSION_INVALID


def test_non_superseding_overlap_is_rejected(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(registry, admin, effective_from=date(2026, 1, 1))
    with pytest.raises(CorpusError) as raised:
        add_version(
            registry,
            admin,
            version_id="version-2",
            effective_from=date(2026, 6, 1),
            activate=True,
        )
    assert raised.value.code is CorpusErrorCode.EFFECTIVE_WINDOW_INVALID


def test_activation_is_idempotent_and_audited_once(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(registry, admin, activate=False)

    first = registry.activate_version(admin, "version-1")
    second = registry.activate_version(admin, "version-1")

    assert first.status is DocumentStatus.ACTIVE
    assert second.status is DocumentStatus.ACTIVE
    assert (
        registry.connection.execute(
            "SELECT COUNT(*) FROM version_activation_events WHERE version_id = 'version-1'"
        ).fetchone()[0]
        == 1
    )


def test_version_content_and_activation_rows_are_immutable(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(registry, admin)

    for statement in (
        "UPDATE document_versions SET version_label = 'changed'",
        "DELETE FROM document_versions",
        "UPDATE version_texts SET canonical_text = 'changed'",
        "DELETE FROM version_texts",
        "DELETE FROM version_activation_events",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            registry.connection.execute(statement)


def test_noncanonical_version_text_is_rejected(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)

    with pytest.raises(CorpusError) as raised:
        registry.add_version(
            admin,
            doc_id="doc-1",
            version_id="version-1",
            version_label="v1",
            source_sha256=sha("version-source"),
            canonical_text="a  b",
            effective_from=date(2026, 1, 1),
        )
    assert raised.value.code is CorpusErrorCode.CANONICALIZATION_MISMATCH


def test_only_fresh_versions_are_authorized_and_stale_versions_are_explicit(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_chunk(
        registry,
        admin,
        doc_id="doc-1",
        family_id="family-1",
        version_id="version-1",
        chunk_id="chunk-a1",
        effective_from=date(2026, 1, 1),
        effective_until=date(2026, 1, 31),
    )
    for doc_id, family_id in (("doc-2", "family-2"), ("doc-3", "family-3")):
        register_document(registry, admin, doc_id=doc_id, family_id=family_id)
        grant(registry, admin, doc_id=doc_id)

    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-2",
        text="The retention period is 45 days.",
        effective_from=date(2026, 2, 1),
        effective_until=date(2026, 10, 31),
        supersedes_version_id="version-1",
        activate=True,
    )
    add_chunk(registry, admin, doc_id="doc-1", version_id="version-2", chunk_id="chunk-a2")
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-3",
        text="The retention period is 60 days.",
        effective_from=date(2026, 11, 1),
        activate=True,
    )
    add_chunk(registry, admin, doc_id="doc-1", version_id="version-3", chunk_id="chunk-a3")
    add_version(registry, admin, doc_id="doc-2", version_id="doc-2-version-1", activate=False)
    add_chunk(registry, admin, doc_id="doc-2", version_id="doc-2-version-1", chunk_id="chunk-b1")
    add_version(
        registry,
        admin,
        doc_id="doc-3",
        version_id="doc-3-version-1",
        text="The retention period is 15 days.",
        effective_from=date(2026, 1, 1),
        effective_until=date(2026, 1, 31),
        activate=True,
    )
    add_chunk(registry, admin, doc_id="doc-3", version_id="doc-3-version-1", chunk_id="chunk-c1")
    grant(registry, admin, doc_id="doc-1")

    authorized = registry.authorized_chunks(user, as_of=AS_OF)
    assert [chunk.chunk_id for chunk in authorized] == ["chunk-a2"]
    stale = registry.stale_chunks(user, as_of=AS_OF)
    assert [chunk.chunk_id for chunk in stale] == ["chunk-a1", "chunk-c1"]
    assert [chunk.status for chunk in stale] == [
        DocumentStatus.SUPERSEDED,
        DocumentStatus.EXPIRED,
    ]
