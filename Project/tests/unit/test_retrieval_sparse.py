from __future__ import annotations

import math

import pytest

from hallx.retrieval import RetrievalError, RetrievalErrorCode, SparseIndex, tokenize
from tests.support import make_evidence_chunk


def index_of(*texts: str) -> SparseIndex:
    return SparseIndex(
        make_evidence_chunk(f"chunk-{chr(ord('a') + position)}", text=text)
        for position, text in enumerate(texts)
    )


def test_tokenizer_is_fixed_and_casefolded() -> None:
    assert tokenize("  The Retention PERIOD is 30 days!  ") == (
        "the",
        "retention",
        "period",
        "is",
        "30",
        "days",
    )
    assert tokenize("snake_case and kebab-case") == ("snake", "case", "and", "kebab", "case")
    assert tokenize("Café Ünïcode") == ("café", "ünïcode")
    assert tokenize("") == ()
    assert tokenize("!!! ...") == ()


def test_bm25_ranks_and_breaks_ties_by_chunk_id() -> None:
    index = index_of(
        "retention period is thirty days",
        "retention period is thirty days",
        "retention retention period period",
    )

    scores = index.search("retention", top_k=5)

    assert [(score.chunk_id, score.rank) for score in scores] == [
        ("chunk-c", 0),
        ("chunk-a", 1),
        ("chunk-b", 2),
    ]
    assert scores[0].score > scores[1].score
    assert scores[1].score == scores[2].score


def test_search_is_independent_of_construction_order() -> None:
    chunks = [
        make_evidence_chunk("chunk-b", text="retention period is thirty days"),
        make_evidence_chunk("chunk-a", text="retention policy"),
        make_evidence_chunk("chunk-c", text="retention retention forever"),
    ]

    forward = SparseIndex(chunks).search("retention policy", top_k=5)
    backward = SparseIndex(reversed(chunks)).search("retention policy", top_k=5)

    assert forward == backward


def test_top_k_truncates_after_deterministic_ranking() -> None:
    index = index_of("retention alpha", "retention beta", "retention gamma")

    assert len(index.search("retention", top_k=1)) == 1
    assert len(index.search("retention", top_k=2)) == 2
    assert len(index.search("retention", top_k=10)) == 3


def test_non_matching_chunks_are_never_returned() -> None:
    index = index_of("alpha beta", "gamma delta")

    assert index.search("epsilon", top_k=5) == ()
    assert [score.chunk_id for score in index.search("alpha", top_k=5)] == ["chunk-a"]
    assert len(index) == 2
    assert index.chunk_ids == ("chunk-a", "chunk-b")


def test_empty_index_searches_to_nothing() -> None:
    index = SparseIndex(())

    assert len(index) == 0
    assert index.search("retention", top_k=1) == ()


def test_index_with_no_tokens_searches_to_nothing() -> None:
    index = index_of("!!!", "___")

    assert len(index) == 2
    assert index.search("retention", top_k=2) == ()


def test_scores_are_finite_and_positive() -> None:
    index = index_of("retention", "retention", "retention")

    for score in index.search("retention", top_k=3):
        assert math.isfinite(score.score)
        assert score.score > 0.0


def test_empty_and_tokenless_queries_fail_closed() -> None:
    index = index_of("retention policy")

    for query in ("", "   ", "\n\t ", "!!!", "_", "___"):
        with pytest.raises(RetrievalError) as raised:
            index.search(query, top_k=1)
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_QUERY_INVALID
        assert str(raised.value) == "RETRIEVAL_QUERY_INVALID: query must contain at least one searchable token"

    with pytest.raises(RetrievalError) as raised:
        index.search(None, top_k=1)  # type: ignore[arg-type]
    assert raised.value.code is RetrievalErrorCode.RETRIEVAL_QUERY_INVALID


def test_invalid_top_k_fails_closed() -> None:
    index = index_of("retention policy")

    for value in (0, -1, True, 1.5, "3"):
        with pytest.raises(RetrievalError) as raised:
            index.search("retention", top_k=value)  # type: ignore[arg-type]
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_TOP_K_INVALID


def test_index_rejects_duplicate_ids_and_non_evidence_chunks() -> None:
    chunk = make_evidence_chunk("chunk-a", text="retention policy")

    with pytest.raises(RetrievalError) as duplicate:
        SparseIndex([chunk, chunk])
    assert duplicate.value.code is RetrievalErrorCode.RETRIEVAL_INDEX_INVALID

    with pytest.raises(RetrievalError) as foreign:
        SparseIndex([object()])  # type: ignore[list-item]
    assert foreign.value.code is RetrievalErrorCode.RETRIEVAL_INDEX_INVALID

    with pytest.raises(RetrievalError) as not_iterable:
        SparseIndex(5)  # type: ignore[arg-type]
    assert not_iterable.value.code is RetrievalErrorCode.RETRIEVAL_INDEX_INVALID
