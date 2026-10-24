"""Corpus registry, ACL policy, version lifecycle, and snapshots."""

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
from hallx.corpus.registry import CORPUS_ADMIN_ROLE, SPLIT_NAMES, CorpusRegistry
from hallx.corpus.schema import SCHEMA_VERSION

__all__ = [
    "CORPUS_ADMIN_ROLE",
    "SCHEMA_VERSION",
    "SPLIT_NAMES",
    "AuthorizationDecision",
    "ChunkRecord",
    "ConflictResolution",
    "CorpusError",
    "CorpusErrorCode",
    "CorpusRegistry",
    "DocumentRecord",
    "SnapshotRecord",
    "VersionRecord",
    "connect",
    "migrate",
    "transaction",
]
