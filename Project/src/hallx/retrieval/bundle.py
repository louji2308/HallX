"""Deterministic identifiers for retrieval bundles and traces.

No wall-clock value enters any identifier. Identical inputs therefore
produce byte-identical bundle and trace IDs on every process restart.
"""

from __future__ import annotations

import hashlib

from hallx.canonical import canonicalize

INDEX_VERSION = "bm25-v1"


def query_sha256(query: str) -> str:
    """Hash the canonical UTF-8 form of a query."""

    canonical = canonicalize(query)
    return hashlib.sha256(canonical.text.encode("utf-8")).hexdigest()


def bundle_id_for(snapshot_id: str, query_digest: str, chunk_ids: tuple[str, ...]) -> str:
    """`bundle-` plus the SHA-256 of the frozen bundle identity payload."""

    joined = "\0".join(sorted(chunk_ids))
    payload = snapshot_id + "\0" + query_digest + "\0" + joined
    return "bundle-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def trace_id_for(bundle_id: str, index_version: str, top_k: int) -> str:
    """`trace-` plus the SHA-256 of the frozen trace identity payload."""

    payload = f"{bundle_id}\0{index_version}\0{top_k}"
    return "trace-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["INDEX_VERSION", "bundle_id_for", "query_sha256", "trace_id_for"]
