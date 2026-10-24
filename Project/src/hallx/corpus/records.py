"""Projection records returned by the corpus registry."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hallx.models import CorpusSnapshot, DocumentStatus

_HEX64 = r"^[0-9a-f]{64}$"


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class DocumentRecord(_Record):
    tenant_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    uploaded_by: str = Field(min_length=1)
    created_at: datetime
    source_sha256: str = Field(pattern=_HEX64)
    authority: str = Field(min_length=1)
    licence: str | None = None
    acl_roles: tuple[str, ...] = ()


class VersionRecord(_Record):
    tenant_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    source_sha256: str = Field(pattern=_HEX64)
    content_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str = Field(min_length=1)
    effective_from: date
    effective_until: date | None = None
    supersedes_version_id: str | None = None
    precedence_rule_id: str | None = None
    created_at: datetime
    created_by: str = Field(min_length=1)
    status: DocumentStatus


class ChunkRecord(_Record):
    tenant_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    original_text: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    canonical_sha256: str = Field(pattern=_HEX64)
    canonicalization_version: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    is_adversarial: bool = False
    created_at: datetime


class SnapshotRecord(_Record):
    tenant_id: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_HEX64)
    created_by: str = Field(min_length=1)
    snapshot: CorpusSnapshot


class ConflictResolution(_Record):
    status: Literal["RESOLVED", "UNRESOLVED", "AMBIGUOUS", "NOT_A_CONFLICT"]
    winner_version_id: str | None = None
    rule_ids: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class AuthorizationDecision(_Record):
    allowed: bool
    reason_code: str = Field(min_length=1)
