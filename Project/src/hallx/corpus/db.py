"""SQLite connection and migration handling for the corpus registry."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from hallx.corpus.errors import CorpusError, CorpusErrorCode
from hallx.corpus.schema import SCHEMA_CHECKSUM, SCHEMA_NAME, SCHEMA_STATEMENTS, SCHEMA_VERSION


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a local database with the required SQLite pragmas."""

    target = str(path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[None]:
    if connection.in_transaction:
        yield
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def migrate(connection: sqlite3.Connection) -> None:
    """Apply the schema once and verify its checksum on every later open."""

    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version == 0:
            applied_at = datetime.now(UTC).isoformat()
            with transaction(connection):
                for statement in SCHEMA_STATEMENTS:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                    "VALUES (?, ?, ?, ?)",
                    (SCHEMA_VERSION, SCHEMA_NAME, SCHEMA_CHECKSUM, applied_at),
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            return
        if version != SCHEMA_VERSION:
            raise CorpusError(
                CorpusErrorCode.SCHEMA_VERSION_UNSUPPORTED,
                "database schema version is not supported",
            )
        row = connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if row is None or row["checksum"] != SCHEMA_CHECKSUM:
            raise CorpusError(
                CorpusErrorCode.MIGRATION_FAILED,
                "database migration checksum does not match",
            )
    except CorpusError:
        raise
    except sqlite3.Error as exc:
        raise CorpusError(
            CorpusErrorCode.MIGRATION_FAILED,
            "database migration failed",
        ) from exc
