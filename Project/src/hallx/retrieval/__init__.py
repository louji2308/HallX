"""ACL-first deterministic sparse retrieval for HallX-Local.

P3B exposes a pure BM25 index, frozen bundle/trace models, and a retriever
that consumes only `CorpusRegistry.authorized_chunks` and
`CorpusRegistry.stale_chunks`. No module here calls a model or the network.
"""

from hallx.retrieval.bundle import INDEX_VERSION, bundle_id_for, query_sha256, trace_id_for
from hallx.retrieval.errors import RetrievalError, RetrievalErrorCode
from hallx.retrieval.models import RetrievalResult, RetrievalTrace, ScoredChunk
from hallx.retrieval.retriever import Retriever
from hallx.retrieval.sparse import SparseIndex, tokenize, validate_top_k

__all__ = [
    "INDEX_VERSION",
    "RetrievalError",
    "RetrievalErrorCode",
    "RetrievalResult",
    "RetrievalTrace",
    "Retriever",
    "ScoredChunk",
    "SparseIndex",
    "bundle_id_for",
    "query_sha256",
    "tokenize",
    "trace_id_for",
    "validate_top_k",
]
