from __future__ import annotations

import importlib
from datetime import date

import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from hallx.models import ConflictPair, Principal
from hallx.retrieval import RetrievalError, RetrievalErrorCode, Retriever
from tests.support_corpus import (
    AS_OF,
    SENTINEL,
    add_chunk,
    add_version,
    grant,
    insert_foreign_principal,
    make_admin,
    make_user,
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


def seed(registry, admin) -> None:
    for doc_id, (family_id, version_id, chunk_id, text, granted) in _DOCS.items():
        register_document(registry, admin, doc_id=doc_id, family_id=family_id, title=doc_id)
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


def setup(registry):
    admin = make_admin(registry)
    seed(registry, admin)
    user = make_user(registry, admin)
    return admin, user, build_snapshot(registry, admin)


def seed_superseded(registry, admin) -> None:
    register_document(registry, admin, doc_id="doc-1", family_id="family-1", title="doc-1")
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


class _SpyRegistry:
    def __init__(self, inner, events: list) -> None:
        self._inner = inner
        self._events = events

    def authorized_chunks(self, actor, *, as_of, snapshot_id=None):
        self._events.append(("authorized_chunks", ()))
        return self._inner.authorized_chunks(actor, as_of=as_of, snapshot_id=snapshot_id)

    def stale_chunks(self, actor, *, as_of, snapshot_id=None):
        self._events.append(("stale_chunks", ()))
        return self._inner.stale_chunks(actor, as_of=as_of, snapshot_id=snapshot_id)


def _install_recording_index(monkeypatch, events: list) -> None:
    module = importlib.import_module("hallx.retrieval.retriever")
    original = module.SparseIndex

    class RecordingIndex(original):
        def __init__(self, chunks) -> None:
            recorded = tuple(chunks)
            events.append(
                (
                    "index",
                    tuple(chunk.chunk_id for chunk in recorded),
                    tuple(chunk.canonical_text for chunk in recorded),
                )
            )
            super().__init__(recorded)

    monkeypatch.setattr(module, "SparseIndex", RecordingIndex)


def test_retrieval_acl_before_ranking(registry, monkeypatch) -> None:
    _, user, snapshot = setup(registry)
    events: list = []
    _install_recording_index(monkeypatch, events)

    result = Retriever(_SpyRegistry(registry, events)).retrieve(
        user,
        SENTINEL,
        as_of=AS_OF,
        snapshot_id=snapshot,
    )

    assert [event[0] for event in events] == ["authorized_chunks", "index", "stale_chunks"]
    indexed_ids = events[1][1]
    assert "chunk-3" not in indexed_ids
    assert set(indexed_ids) == {"chunk-1", "chunk-2"}
    assert "chunk-3" not in tuple(chunk.chunk_id for chunk in result.bundle.chunks)
    assert "chunk-3" not in tuple(chunk.chunk_id for chunk in result.bundle.stale_candidates)
    assert "chunk-3" not in tuple(score.chunk_id for score in result.trace.scores)


def test_retrieval_restricted_text_never_enters_index(registry, monkeypatch) -> None:
    _, user, snapshot = setup(registry)
    events: list = []
    _install_recording_index(monkeypatch, events)

    Retriever(registry).retrieve(
        user,
        "retention period",
        as_of=AS_OF,
        snapshot_id=snapshot,
    )

    index_events = [event for event in events if event[0] == "index"]
    assert len(index_events) == 1
    indexed_ids = index_events[0][1]
    indexed_texts = index_events[0][2]
    assert "chunk-3" not in indexed_ids
    assert all(SENTINEL not in text for text in indexed_texts)


def test_retrieval_restricted_chunk_not_selected(registry) -> None:
    _, user, snapshot = setup(registry)

    result = Retriever(registry).retrieve(
        user,
        f"{SENTINEL} retention",
        as_of=AS_OF,
        snapshot_id=snapshot,
        top_k=10,
    )

    assert result.trace.candidate_count == 2
    assert tuple(chunk.chunk_id for chunk in result.bundle.chunks) == ("chunk-1", "chunk-2")
    assert "chunk-3" not in tuple(score.chunk_id for score in result.trace.scores)
    assert "chunk-3" not in result.trace.stale_chunk_ids
    assert result.bundle.stale_candidates == ()


def test_retrieval_acl_revocation_removes_chunks(registry) -> None:
    admin, user, snapshot = setup(registry)
    retriever = Retriever(registry)

    before = retriever.retrieve(user, "retention", as_of=AS_OF, snapshot_id=snapshot)
    assert tuple(chunk.chunk_id for chunk in before.bundle.chunks) == ("chunk-1", "chunk-2")

    registry.revoke_acl(admin, "doc-1", ("analyst",))
    after = retriever.retrieve(user, "retention", as_of=AS_OF, snapshot_id=snapshot)

    assert tuple(chunk.chunk_id for chunk in after.bundle.chunks) == ("chunk-2",)
    assert after.trace.candidate_count == 1
    assert "chunk-1" not in after.trace.selected_chunk_ids


def test_retrieval_stale_path_respects_revocation(registry) -> None:
    admin = make_admin(registry)
    seed_superseded(registry, admin)
    user = make_user(registry, admin)
    snapshot = build_snapshot(registry, admin, families=("family-1",))
    retriever = Retriever(registry)

    before = retriever.retrieve(user, "retention", as_of=AS_OF, snapshot_id=snapshot)
    assert tuple(chunk.chunk_id for chunk in before.bundle.chunks) == ("chunk-new",)
    assert before.trace.stale_chunk_ids == ("chunk-old",)

    registry.revoke_acl(admin, "doc-1", ("analyst",))
    after = retriever.retrieve(user, "retention", as_of=AS_OF, snapshot_id=snapshot)

    assert after.bundle.chunks == ()
    assert after.bundle.stale_candidates == ()
    assert after.trace.candidate_count == 0
    assert after.trace.stale_chunk_ids == ()


def test_retrieval_cross_tenant_is_denied(registry) -> None:
    _, _, snapshot = setup(registry)
    insert_foreign_principal(
        registry,
        principal_id="other-user",
        tenant_id="tenant-b",
        roles=("analyst",),
    )
    other = Principal(principal_id="other-user", tenant_id="tenant-b", roles=("analyst",))

    with pytest.raises(CorpusError) as raised:
        Retriever(registry).retrieve(
            other,
            "retention",
            as_of=AS_OF,
            snapshot_id=snapshot,
        )

    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
    assert SENTINEL not in str(raised.value)


def test_retrieval_rejects_forged_tenant_actor(registry) -> None:
    _, _, snapshot = setup(registry)
    forged = Principal(principal_id="user-1", tenant_id="tenant-b", roles=("analyst",))

    with pytest.raises(RetrievalError) as raised:
        Retriever(registry).retrieve(
            forged,
            "retention",
            as_of=AS_OF,
            snapshot_id=snapshot,
        )

    assert raised.value.code is RetrievalErrorCode.RETRIEVAL_TENANT_MISMATCH
    assert SENTINEL not in str(raised.value)


def test_retrieval_cannot_target_restricted_chunk_via_conflicts(registry) -> None:
    _, user, snapshot = setup(registry)
    pair = ConflictPair(
        chunk_id_a="chunk-1",
        chunk_id_b="chunk-3",
        reason="Attempt to force a restricted chunk into the bundle.",
    )

    with pytest.raises(RetrievalError) as raised:
        Retriever(registry).retrieve(
            user,
            "retention",
            as_of=AS_OF,
            snapshot_id=snapshot,
            conflict_pairs=(pair,),
        )

    assert raised.value.code is RetrievalErrorCode.RETRIEVAL_CONFLICT_INVALID
    assert SENTINEL not in str(raised.value)
