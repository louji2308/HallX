import sqlite3

import pytest

from hallx.corpus import (
    SCHEMA_VERSION,
    CorpusError,
    CorpusErrorCode,
    CorpusRegistry,
    connect,
    migrate,
)


def test_migration_is_idempotent_and_checksum_verified(tmp_path) -> None:
    path = tmp_path / "corpus.db"
    first = CorpusRegistry.open(path)
    try:
        assert first.connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert first.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert first.connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
    finally:
        first.close()

    second = CorpusRegistry.open(path)
    try:
        assert second.connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
    finally:
        second.close()


def test_migration_checksum_mismatch_fails_closed(tmp_path) -> None:
    path = tmp_path / "corpus.db"
    registry = CorpusRegistry.open(path)
    registry.connection.execute("UPDATE schema_migrations SET checksum = ?", ("0" * 64,))
    registry.close()

    with pytest.raises(CorpusError) as raised:
        CorpusRegistry.open(path)
    assert raised.value.code is CorpusErrorCode.MIGRATION_FAILED


def test_unknown_schema_version_fails_closed(tmp_path) -> None:
    path = tmp_path / "future.db"
    connection = connect(path)
    connection.execute("PRAGMA user_version = 2")
    try:
        with pytest.raises(CorpusError) as raised:
            migrate(connection)
        assert raised.value.code is CorpusErrorCode.SCHEMA_VERSION_UNSUPPORTED
    finally:
        connection.close()


def test_foreign_keys_are_enforced(tmp_path) -> None:
    connection = connect(tmp_path / "corpus.db")
    migrate(connection)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO principal_roles(principal_id, role, granted_at, granted_by) "
                "VALUES ('missing', 'analyst', 'now', 'admin')"
            )
    finally:
        connection.close()


def test_content_tables_reject_update_and_delete(tmp_path) -> None:
    from tests.support_corpus import (
        add_version,
        make_admin,
        open_registry,
        register_document,
    )

    registry = open_registry(tmp_path)
    try:
        admin = make_admin(registry)
        register_document(registry, admin)
        add_version(registry, admin)

        for statement in (
            "UPDATE documents SET title = 'changed'",
            "DELETE FROM documents",
            "UPDATE document_versions SET version_label = 'changed'",
            "DELETE FROM document_versions",
            "UPDATE version_texts SET canonical_text = 'changed'",
            "DELETE FROM version_texts",
            "DELETE FROM version_activation_events",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                registry.connection.execute(statement)
    finally:
        registry.close()
