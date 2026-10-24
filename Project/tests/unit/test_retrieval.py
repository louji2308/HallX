from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from hallx.canonical import canonicalize
from hallx.corpus import CorpusError, CorpusErrorCode
from hallx.models import ConflictPair, DocumentStatus
from hallx.retrieval import (
    RetrievalError,
    RetrievalErrorCode,
    RetrievalResult,
    RetrievalTrace,
    Retriever,
    ScoredChunk,
)
from tests.support_corpus import (
    AS_OF,
    SENTINEL,
    add_chunk,
    add_version,
    grant,
    make_admin,
    make_user,
    open_registry,
    register_document,
    registry_fixture,
)

registry = registry_fixture

_DOCS = {
    "doc-1": ("family-1", "version-1", "chunk-1", "The retention period is 30 days.", True),
    "doc-2": (
        "family-2",
        "version-2",
        "chunk-2",
        "The retention period is 45 days for legal holds.",
        True,
    ),
    "doc-3": (
        "family-3",
        "version-3",
        "chunk-3",
        f"{SENTINEL} sets the retention period to 99 days.",
        False,
    ),
}


def seed(registry, admin, *, order=("doc-1", "doc-2", "doc-3")) -> None:
    for doc_id in order:
        family_id, version_id, chunk_id, text, granted = _DOCS[doc_id]
        register_document(registry, admin, doc_id=doc_id, family_id=family_id, title=text)
        add_version(registry, admin, doc_id=doc_id, version_id=version_id, text=text)
        add_chunk(
            registry,
            admin,
            doc_id=doc_id,
            version_id=version_id,
            chunk_id=chunk_id,
            text=text,
        )
        if granted:
            grant(registry, admin, doc_id=doc_id, roles=("analyst",))


def build_snapshot(registry, admin, *, families=None) -> str:
    for family_id in families or tuple(spec[0] for spec in _DOCS.values()):
        registry.assign_split(admin, family_id, "train")
    return registry.build_snapshot(admin).snapshot.snapshot_id


def setup(registry, *, order=("doc-1", "doc-2", "doc-3")):
    admin = make_admin(registry)
    seed(registry, admin, order=order)
    user = make_user(registry, admin)
    return admin, user, build_snapshot(registry, admin)


def expected_bundle_id(snapshot_id: str, query: str, chunk_ids: tuple[str, ...]) -> str:
    digest = hashlib.sha256(canonicalize(query).text.encode("utf-8")).hexdigest()
    payload = snapshot_id + "\0" + digest + "\0" + "\0".join(sorted(chunk_ids))
    return "bundle-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def expected_trace_id(bundle_id: str, top_k: int) -> str:
    payload = bundle_id + "\0bm25-v1\0" + str(top_k)
    return "trace-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_retrieval_returns_authorized_active_chunks(registry) -> None:
    _, user, snapshot = setup(registry)

    result = Retriever(registry).retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
        include_stale=False,
    )

    selected_ids = tuple(chunk.chunk_id for chunk in result.bundle.chunks)
    assert selected_ids == ("chunk-1", "chunk-2")
    assert all(chunk.status is DocumentStatus.ACTIVE for chunk in result.bundle.chunks)
    assert result.bundle.tenant_id == user.tenant_id
    assert result.bundle.snapshot_id == snapshot
    assert result.trace.snapshot_id == snapshot
    assert result.trace.as_of == AS_OF
    assert result.trace.index_version == "bm25-v1"
    assert result.trace.candidate_count == 2
    assert tuple(score.chunk_id for score in result.trace.scores) == selected_ids
    assert tuple(score.rank for score in result.trace.scores) == (0, 1)
    assert result.trace.scores[0].score > result.trace.scores[1].score
    assert result.bundle.bundle_id == expected_bundle_id(snapshot, "retention period", selected_ids)
    assert result.trace.trace_id == expected_trace_id(result.bundle.bundle_id, 8)


def test_retrieval_bundle_reproducible_across_registries(tmp_path) -> None:
    first = open_registry(tmp_path / "first")
    second = open_registry(tmp_path / "second")
    try:
        first_admin = make_admin(first)
        seed(first, first_admin)
        second_admin = make_admin(second)
        seed(second, second_admin, order=("doc-3", "doc-2", "doc-1"))
        first_user = make_user(first, first_admin)
        second_user = make_user(second, second_admin)
        first_snapshot = build_snapshot(first, first_admin)
        second_snapshot = build_snapshot(second, second_admin)
        assert first_snapshot == second_snapshot

        first_result = Retriever(first).retrieve(
            first_user,
            "retention period",
            as_of=AS_OF,
            snapshot_id=first_snapshot,
        )
        second_result = Retriever(second).retrieve(
            second_user,
            "retention   period",
            as_of=AS_OF,
            snapshot_id=second_snapshot,
        )

        assert first_result == second_result
        assert first_result.bundle.bundle_id == second_result.bundle.bundle_id
        assert first_result.trace.trace_id == second_result.trace.trace_id
        assert first_result == Retriever(first).retrieve(
            first_user,
            "retention period",
            as_of=AS_OF,
            snapshot_id=first_snapshot,
        )
    finally:
        first.close()
        second.close()


def test_retrieval_snapshot_filter_is_closed(registry) -> None:
    admin, user, first_snapshot = setup(registry)
    retriever = Retriever(registry)
    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        chunk_id="chunk-4",
        chunk_index=1,
        text="Retention addendum requirements apply.",
    )

    before = retriever.retrieve(
        user,
        "retention",
        as_of=AS_OF,
        snapshot_id=first_snapshot,
        include_stale=False,
    )
    assert "chunk-4" not in tuple(chunk.chunk_id for chunk in before.bundle.chunks)
    assert before.trace.candidate_count == 2

    second_snapshot = build_snapshot(registry, admin)
    assert second_snapshot != first_snapshot
    after = retriever.retrieve(
        user,
        "retention",
        as_of=AS_OF,
        snapshot_id=second_snapshot,
        include_stale=False,
    )
    assert "chunk-4" in tuple(chunk.chunk_id for chunk in after.bundle.chunks)
    assert after.trace.candidate_count == 3


def test_retrieval_stale_is_diagnostic_only(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1")
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-old",
        text="The legacy retention period is 30 days.",
        effective_from=date(2026, 1, 1),
    )
    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-old",
        chunk_id="chunk-old",
        text="The legacy retention period is 30 days.",
    )
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-new",
        text="The current retention period is 60 days.",
        effective_from=date(2026, 6, 1),
        supersedes_version_id="version-old",
    )
    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-new",
        chunk_id="chunk-new",
        text="The current retention period is 60 days.",
    )
    grant(registry, admin, doc_id="doc-1", roles=("analyst",))
    user = make_user(registry, admin)
    snapshot = build_snapshot(registry, admin, families=("family-1",))
    retriever = Retriever(registry)

    stale_match = retriever.retrieve(
        user,
        "legacy",
        as_of=AS_OF,
        snapshot_id=snapshot,
        include_stale=True,
    )
    assert stale_match.bundle.chunks == ()
    assert stale_match.trace.scores == ()
    assert tuple(chunk.chunk_id for chunk in stale_match.bundle.stale_candidates) == ("chunk-old",)
    assert stale_match.bundle.stale_candidates[0].status is DocumentStatus.SUPERSEDED
    assert stale_match.trace.stale_chunk_ids == ("chunk-old",)

    active_match = retriever.retrieve(
        user,
        "retention",
        as_of=AS_OF,
        snapshot_id=snapshot,
        include_stale=True,
    )
    assert tuple(chunk.chunk_id for chunk in active_match.bundle.chunks) == ("chunk-new",)
    assert "chunk-old" not in tuple(chunk.chunk_id for chunk in active_match.bundle.chunks)
    assert "chunk-old" not in tuple(score.chunk_id for score in active_match.trace.scores)
    assert active_match.trace.stale_chunk_ids == ("chunk-old",)

    without_stale = retriever.retrieve(
        user,
        "retention",
        as_of=AS_OF,
        snapshot_id=snapshot,
        include_stale=False,
    )
    assert without_stale.bundle.stale_candidates == ()
    assert without_stale.trace.stale_chunk_ids == ()


def test_retrieval_no_match_returns_empty_bundle(registry) -> None:
    _, user, snapshot = setup(registry)

    result = Retriever(registry).retrieve(
        user,
        "unfindableterm",
        as_of=AS_OF,
        snapshot_id=snapshot,
    )

    assert result.bundle.chunks == ()
    assert result.trace.selected_chunk_ids == ()
    assert result.trace.scores == ()
    assert result.trace.stale_chunk_ids == ()
    assert result.trace.candidate_count == 2
    assert result.bundle.bundle_id == expected_bundle_id(snapshot, "unfindableterm", ())


def test_retrieval_top_k_limits_selection(registry) -> None:
    _, user, snapshot = setup(registry)
    retriever = Retriever(registry)

    limited = retriever.retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
        top_k=1,
    )
    assert tuple(chunk.chunk_id for chunk in limited.bundle.chunks) == ("chunk-1",)
    assert limited.trace.top_k == 1
    assert len(limited.trace.scores) == 1
    assert limited.trace.candidate_count == 2

    expanded = retriever.retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
        top_k=10,
    )
    assert len(expanded.bundle.chunks) == 2
    assert expanded.trace.top_k == 10


def test_retrieval_conflict_pairs_must_reference_selected_chunks(registry) -> None:
    _, user, snapshot = setup(registry)
    retriever = Retriever(registry)
    valid = ConflictPair(
        chunk_id_a="chunk-1",
        chunk_id_b="chunk-2",
        reason="Competing retention periods.",
    )
    result = retriever.retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
        conflict_pairs=(valid,),
    )
    assert result.bundle.conflict_pairs == (valid,)

    for pair in (
        ConflictPair(chunk_id_a="chunk-1", chunk_id_b="chunk-3", reason="Restricted."),
        ConflictPair(chunk_id_a="chunk-1", chunk_id_b="missing", reason="Unknown."),
    ):
        with pytest.raises(RetrievalError) as raised:
            retriever.retrieve(
                user,
                "retention period",
                as_of=AS_OF,
                snapshot_id=snapshot,
                conflict_pairs=(pair,),
            )
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID

    with pytest.raises(RetrievalError) as malformed:
        retriever.retrieve(
            user,
            "retention period",
            as_of=AS_OF,
            snapshot_id=snapshot,
            conflict_pairs=(("chunk-1", "chunk-2"),),  # type: ignore[arg-type]
        )
    assert malformed.value.code is RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID


def test_retrieval_invalid_inputs_fail_closed(registry) -> None:
    _, user, snapshot = setup(registry)
    retriever = Retriever(registry)

    for query in ("", "   ", "\n\t", "!!!", "_"):
        with pytest.raises(RetrievalError) as raised:
            retriever.retrieve(user, query, as_of=AS_OF, snapshot_id=snapshot)
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_QUERY_INVALID

    with pytest.raises(RetrievalError) as no_query:
        retriever.retrieve(user, None, as_of=AS_OF, snapshot_id=snapshot)  # type: ignore[arg-type]
    assert no_query.value.code is RetrievalErrorCode.RETRIEVAL_QUERY_INVALID

    for value in (0, -1, True, 1.5):
        with pytest.raises(RetrievalError) as raised:
            retriever.retrieve(
                user,
                "retention",
                as_of=AS_OF,
                snapshot_id=snapshot,
                top_k=value,  # type: ignore[arg-type]
            )
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_TOP_K_INVALID

    for value in (None, "", "   "):
        with pytest.raises(RetrievalError) as raised:
            retriever.retrieve(user, "retention", as_of=AS_OF, snapshot_id=value)
        assert raised.value.code is RetrievalErrorCode.RETRIEVAL_SNAPSHOT_INVALID

    with pytest.raises(RetrievalError) as raised:
        retriever.retrieve(
            user,
            "retention",
            as_of=datetime(2026, 10, 24, 12, 0, tzinfo=UTC),  # type: ignore[arg-type]
            snapshot_id=snapshot,
        )
    assert raised.value.code is RetrievalErrorCode.RETRIEVAL_AS_OF_INVALID

    with pytest.raises(CorpusError) as missing:
        retriever.retrieve(
            user,
            "retention",
            as_of=AS_OF,
            snapshot_id="snap-does-not-exist",
        )
    assert missing.value.code is CorpusErrorCode.CORPUS_NOT_FOUND


def test_retrieval_does_not_leak_text(registry, caplog) -> None:
    _, user, snapshot = setup(registry)
    caplog.set_level(logging.DEBUG)
    query = f"{SENTINEL} retention"

    result = Retriever(registry).retrieve(user, query, as_of=AS_OF, snapshot_id=snapshot)
    rendered = result.model_dump_json() + repr(result) + repr(result.trace)
    assert SENTINEL not in rendered
    assert SENTINEL not in result.trace.query_sha256

    with pytest.raises(RetrievalError) as raised:
        Retriever(registry).retrieve(
            user,
            query,
            as_of=AS_OF,
            snapshot_id=snapshot,
            top_k=0,
        )
    assert SENTINEL not in str(raised.value)

    for record in caplog.records:
        assert SENTINEL not in record.getMessage()

    leaked = Retriever(registry).retrieve(
        user,
        "retention",
        as_of=AS_OF,
        snapshot_id=snapshot,
    )
    assert SENTINEL not in leaked.model_dump_json()


def test_retrieval_result_models_fail_closed(registry) -> None:
    _, user, snapshot = setup(registry)
    result = Retriever(registry).retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
        include_stale=False,
    )
    active, other = result.bundle.chunks
    scores = (
        ScoredChunk(chunk_id=active.chunk_id, score=1.0, rank=0),
        ScoredChunk(chunk_id=other.chunk_id, score=0.5, rank=1),
    )
    trace = RetrievalTrace(
        trace_id="trace-1",
        query_sha256="0" * 64,
        snapshot_id=snapshot,
        as_of=AS_OF,
        index_version="bm25-v1",
        candidate_count=2,
        selected_chunk_ids=(active.chunk_id, other.chunk_id),
        stale_chunk_ids=(),
        top_k=2,
        scores=scores,
    )
    assert RetrievalResult(bundle=result.bundle, trace=trace).trace.top_k == 2

    with pytest.raises(ValidationError):
        RetrievalTrace(
            trace_id="trace-1",
            query_sha256="0" * 64,
            snapshot_id=snapshot,
            as_of=AS_OF,
            index_version="bm25-v1",
            candidate_count=2,
            selected_chunk_ids=(active.chunk_id,),
            stale_chunk_ids=(),
            top_k=0,
            scores=(scores[0],),
        )

    with pytest.raises(ValidationError):
        RetrievalResult(
            bundle=result.bundle.model_copy(update={"snapshot_id": "snap-other"}),
            trace=trace,
        )

    with pytest.raises(ValidationError):
        RetrievalResult(
            bundle=result.bundle,
            trace=trace.model_copy(update={"selected_chunk_ids": (other.chunk_id, active.chunk_id)}),
        )
