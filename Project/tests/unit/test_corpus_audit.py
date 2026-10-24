import sqlite3
from datetime import date

import pytest

from hallx.corpus import CorpusError
from tests.support_corpus import (
    SENTINEL,
    add_chunk,
    add_version,
    audit_rows,
    grant,
    make_admin,
    make_user,
    register_document,
    registry_fixture,
    seed_chunk,
)

registry = registry_fixture


def test_mutations_append_audit_rows(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    grant(registry, admin, doc_id="doc-1")
    registry.assign_split(admin, "family-1", "train")
    registry.build_snapshot(admin)

    actions = [row["action"] for row in audit_rows(registry)]
    for action in (
        "PRINCIPAL_CREATED",
        "DOCUMENT_REGISTERED",
        "VERSION_CREATED",
        "CHUNK_CREATED",
        "ACL_GRANTED",
        "SPLIT_ASSIGNED",
        "SNAPSHOT_CREATED",
    ):
        assert action in actions
    assert user.roles == ("analyst",)


def test_audit_rows_are_append_only(registry) -> None:
    make_admin(registry)
    for statement in (
        "UPDATE audit_events SET reason_code = 'changed'",
        "DELETE FROM audit_events",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            registry.connection.execute(statement)


def test_audit_metadata_and_errors_never_contain_chunk_text(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1", title=SENTINEL)
    add_version(registry, admin, doc_id="doc-1", version_id="version-1", text=SENTINEL)
    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        chunk_id="chunk-1",
        text=SENTINEL,
    )

    with pytest.raises(CorpusError) as raised:
        registry.get_authorized_chunk(user, "chunk-1", as_of=date(2026, 10, 24))
    assert SENTINEL not in str(raised.value)
    for row in audit_rows(registry):
        assert SENTINEL not in row["metadata_json"]
