"""Typed error codes and validation issues for the deterministic core.

Messages are deliberately bounded: they may name IDs and rule codes but must
never include restricted source text or evidence quotes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ErrorCode(str, Enum):
    # Schema and bundle integrity
    SCHEMA_INVALID = "SCHEMA_INVALID"
    BUNDLE_EMPTY = "BUNDLE_EMPTY"
    DUPLICATE_CHUNK_ID = "DUPLICATE_CHUNK_ID"
    TRIAGE_INCOMPLETE = "TRIAGE_INCOMPLETE"
    TRIAGE_DUPLICATE = "TRIAGE_DUPLICATE"
    TRIAGE_UNKNOWN_CHUNK = "TRIAGE_UNKNOWN_CHUNK"
    TRIAGE_IDENTITY_MISMATCH = "TRIAGE_IDENTITY_MISMATCH"
    CHUNK_HASH_MISMATCH = "CHUNK_HASH_MISMATCH"
    CANONICALIZATION_MISMATCH = "CANONICALIZATION_MISMATCH"
    SOURCE_MAP_UNSUPPORTED = "SOURCE_MAP_UNSUPPORTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Quote and claim checks
    QUOTE_EMPTY = "QUOTE_EMPTY"
    QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
    QUOTE_AMBIGUOUS = "QUOTE_AMBIGUOUS"
    UNKNOWN_CHUNK = "UNKNOWN_CHUNK"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    CLAIM_TRIAGE_MISMATCH = "CLAIM_TRIAGE_MISMATCH"
    ADVERSARIAL_EVIDENCE = "ADVERSARIAL_EVIDENCE"
    CITATION_NOT_ENTAILED = "CITATION_NOT_ENTAILED"
    NUMERIC_MISMATCH = "NUMERIC_MISMATCH"

    # Authorization, identity, and freshness
    ACL_DENIED = "ACL_DENIED"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    SOURCE_NOT_ACTIVE = "SOURCE_NOT_ACTIVE"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_EXPIRED = "SOURCE_EXPIRED"

    # State and diagnostics
    CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"
    CONFLICT_DIAGNOSTIC_MISSING = "CONFLICT_DIAGNOSTIC_MISSING"
    STALE_DIAGNOSTIC_MISSING = "STALE_DIAGNOSTIC_MISSING"
    PARTIAL_DIAGNOSTICS_REQUIRED = "PARTIAL_DIAGNOSTICS_REQUIRED"
    MISSING_DIAGNOSTICS_REQUIRED = "MISSING_DIAGNOSTICS_REQUIRED"
    SUMMARY_UNSUPPORTED = "SUMMARY_UNSUPPORTED"
    EVIDENCE_STATE_MISMATCH = "EVIDENCE_STATE_MISMATCH"


class ValidationIssue(BaseModel):
    """A single deterministic validation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode
    severity: Severity = Severity.ERROR
    message: str
    chunk_id: str | None = None
    claim_index: int | None = None

    @property
    def blocking(self) -> bool:
        return self.severity is Severity.ERROR


REPAIRABLE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.QUOTE_NOT_FOUND,
        ErrorCode.NUMERIC_MISMATCH,
        ErrorCode.CITATION_NOT_ENTAILED,
        ErrorCode.TRIAGE_INCOMPLETE,
        ErrorCode.PARTIAL_DIAGNOSTICS_REQUIRED,
        ErrorCode.CONFLICT_DIAGNOSTIC_MISSING,
        ErrorCode.MISSING_DIAGNOSTICS_REQUIRED,
    }
)

NEVER_REPAIRABLE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.ACL_DENIED,
        ErrorCode.TENANT_MISMATCH,
        ErrorCode.SOURCE_IDENTITY_MISMATCH,
        ErrorCode.UNKNOWN_CHUNK,
        ErrorCode.SOURCE_NOT_ACTIVE,
        ErrorCode.SOURCE_STALE,
        ErrorCode.SOURCE_EXPIRED,
        ErrorCode.ADVERSARIAL_EVIDENCE,
        ErrorCode.QUOTE_AMBIGUOUS,
        ErrorCode.SOURCE_MAP_UNSUPPORTED,
        ErrorCode.CHUNK_HASH_MISMATCH,
        ErrorCode.CANONICALIZATION_MISMATCH,
        ErrorCode.CONFLICT_UNRESOLVED,
        ErrorCode.DUPLICATE_CHUNK_ID,
        ErrorCode.TRIAGE_DUPLICATE,
        ErrorCode.TRIAGE_UNKNOWN_CHUNK,
        ErrorCode.TRIAGE_IDENTITY_MISMATCH,
        ErrorCode.BUNDLE_EMPTY,
        ErrorCode.SCHEMA_INVALID,
    }
)


def issue(
    code: ErrorCode,
    message: str,
    *,
    chunk_id: str | None = None,
    claim_index: int | None = None,
    severity: Severity = Severity.ERROR,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        message=message,
        chunk_id=chunk_id,
        claim_index=claim_index,
    )


class SpanResolutionError(ValueError):
    """A quote could not be resolved to exactly one canonical span."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class SourceMapError(ValueError):
    """A canonical span cannot be mapped back to original source text."""
