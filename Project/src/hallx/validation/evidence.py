"""Bundle integrity, ACL, and source-identity checks."""

from __future__ import annotations

import hashlib
from datetime import date

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize
from hallx.errors import ErrorCode, SourceMapError, ValidationIssue, issue
from hallx.models import DocumentStatus, EvidenceBundle, EvidenceChunk, Principal


def principal_has_access(chunk: EvidenceChunk, principal: Principal) -> bool:
    if chunk.tenant_id != principal.tenant_id:
        return False
    return bool(set(chunk.acl_roles).intersection(principal.roles))


def is_fresh(chunk: EvidenceChunk, as_of: date) -> bool:
    return (
        chunk.status is DocumentStatus.ACTIVE
        and chunk.effective_from <= as_of
        and (chunk.effective_until is None or as_of <= chunk.effective_until)
    )


def validate_evidence_bundle(
    bundle: EvidenceBundle, principal: Principal
) -> tuple[ValidationIssue, ...]:
    """Check the bundle before any model output is trusted.

    Restricted or stale chunks never become valid evidence. The caller must
    reject with no final state when any blocking issue is returned.
    """

    issues: list[ValidationIssue] = []

    if not bundle.chunks and not bundle.stale_candidates:
        issues.append(issue(ErrorCode.BUNDLE_EMPTY, "evidence bundle contains no chunks"))
    if bundle.tenant_id != principal.tenant_id:
        issues.append(
            issue(
                ErrorCode.TENANT_MISMATCH,
                "bundle tenant does not match the requesting principal",
            )
        )

    seen: set[str] = set()
    for chunk in bundle.chunks:
        if chunk.chunk_id in seen:
            issues.append(
                issue(
                    ErrorCode.DUPLICATE_CHUNK_ID,
                    "bundle contains a duplicate chunk id",
                    chunk_id=chunk.chunk_id,
                )
            )
            continue
        seen.add(chunk.chunk_id)

        if chunk.tenant_id != principal.tenant_id:
            issues.append(
                issue(
                    ErrorCode.TENANT_MISMATCH,
                    "chunk tenant does not match the requesting principal",
                    chunk_id=chunk.chunk_id,
                )
            )
        if not principal_has_access(chunk, principal):
            issues.append(
                issue(
                    ErrorCode.ACL_DENIED,
                    "principal lacks a role admitted by the chunk ACL",
                    chunk_id=chunk.chunk_id,
                )
            )
            continue

        if chunk.status is not DocumentStatus.ACTIVE:
            issues.append(
                issue(
                    ErrorCode.SOURCE_NOT_ACTIVE,
                    "chunk version is not active",
                    chunk_id=chunk.chunk_id,
                )
            )
        if chunk.canonicalization_version != CANONICALIZATION_VERSION:
            issues.append(
                issue(
                    ErrorCode.CANONICALIZATION_MISMATCH,
                    "chunk canonicalization version is not supported",
                    chunk_id=chunk.chunk_id,
                )
            )
            continue

        expected = hashlib.sha256(chunk.canonical_text.encode("utf-8")).hexdigest()
        if expected != chunk.canonical_sha256:
            issues.append(
                issue(
                    ErrorCode.CHUNK_HASH_MISMATCH,
                    "chunk canonical hash does not match its text",
                    chunk_id=chunk.chunk_id,
                )
            )

        regenerated = canonicalize(chunk.original_text)
        if regenerated.text != chunk.canonical_text:
            issues.append(
                issue(
                    ErrorCode.CANONICALIZATION_MISMATCH,
                    "chunk canonical text does not match canonicalization of its source",
                    chunk_id=chunk.chunk_id,
                )
            )
            continue
        try:
            regenerated.to_original_span(0, len(regenerated.text))
        except SourceMapError:
            issues.append(
                issue(
                    ErrorCode.SOURCE_MAP_UNSUPPORTED,
                    "chunk source cannot be mapped to original text",
                    chunk_id=chunk.chunk_id,
                )
            )

    return tuple(issues)
