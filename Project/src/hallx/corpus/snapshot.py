"""Deterministic corpus snapshot manifest and hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

MANIFEST_VERSION = "hallx-corpus-manifest-v1"
MANIFEST_PREFIX = b"hallx.corpus.manifest.v1\n"
CONTENT_PREFIX = b"hallx.corpus.content.v1\n"
SPLIT_PREFIX = b"hallx.corpus.split.v1\n"


@dataclass(frozen=True, slots=True)
class SnapshotHashes:
    manifest_sha256: str
    content_sha256: str
    split_lock_sha256: str


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _hash(prefix: bytes, payload: Any) -> str:
    return hashlib.sha256(prefix + canonical_json(payload).encode("utf-8")).hexdigest()


def content_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "documents": manifest["documents"],
        "versions": manifest["versions"],
        "chunks": manifest["chunks"],
    }


def split_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"splits": manifest["splits"]}


def compute_hashes(manifest: dict[str, Any]) -> SnapshotHashes:
    return SnapshotHashes(
        manifest_sha256=_hash(MANIFEST_PREFIX, manifest),
        content_sha256=_hash(CONTENT_PREFIX, content_projection(manifest)),
        split_lock_sha256=_hash(SPLIT_PREFIX, split_projection(manifest)),
    )


def snapshot_id_for(manifest_sha256: str) -> str:
    return f"snap-{manifest_sha256}"


def verify_manifest_hashes(manifest: dict[str, Any], hashes: SnapshotHashes) -> bool:
    actual = compute_hashes(manifest)
    return actual == hashes
