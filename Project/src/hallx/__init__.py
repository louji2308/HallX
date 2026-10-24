"""HallX-Local deterministic core.

Phase 1 exposes the evidence contract, canonicalization, source maps, and
server-side validation. No module in this package calls a model or network.
"""

from hallx.canonical import CANONICALIZATION_VERSION, CanonicalDocument, canonicalize
from hallx.errors import ErrorCode, Severity, ValidationIssue
from hallx.models import (
    AbstentionAndConflictDiagnosis,
    Chunk,
    ConflictPair,
    CorpusSnapshot,
    Document,
    DocumentStatus,
    DocumentVersion,
    EntailmentResult,
    EvidenceBundle,
    EvidenceChunk,
    EvidenceState,
    GenerationChunkTriage,
    GenerationClaim,
    GenerationProofEnvelope,
    Principal,
    TriageStatus,
    ValidatedClaim,
    ValidatedProofEnvelope,
    ValidationResult,
)

__all__ = [
    "CANONICALIZATION_VERSION",
    "AbstentionAndConflictDiagnosis",
    "CanonicalDocument",
    "Chunk",
    "ConflictPair",
    "CorpusSnapshot",
    "Document",
    "DocumentStatus",
    "DocumentVersion",
    "EntailmentResult",
    "ErrorCode",
    "EvidenceBundle",
    "EvidenceChunk",
    "EvidenceState",
    "GenerationChunkTriage",
    "GenerationClaim",
    "GenerationProofEnvelope",
    "Principal",
    "Severity",
    "TriageStatus",
    "ValidatedClaim",
    "ValidatedProofEnvelope",
    "ValidationIssue",
    "ValidationResult",
    "canonicalize",
]
