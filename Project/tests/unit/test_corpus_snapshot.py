import sqlite3

import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from tests.support_corpus import (
    AS_OF,
    add_chunk,
    add_version,
    grant,
    make_admin,
    open_registry,
    register_document,
    registry_fixture,
    seed_chunk,
)

registry = registry_fixture


def test_snapshot_is_reproducible_across_insertion_order(tmp_path) -> None:
    first_registry = open_registry(tmp_path / "one")
    second_registry = open_registry(tmp_path / "two")
    try:
        first_admin = make_admin(first_registry)
        second_admin = make_admin(second_registry)

        for doc_id, family_id in (("doc-1", "family-1"), ("doc-2", "family-2")):
            register_document(first_registry, first_admin, doc_id=doc_id, family_id=family_id)
        for doc_id, family_id in (("doc-2", "family-2"), ("doc-1", "family-1")):
            register_document(second_registry, second_admin, doc_id=doc_id, family_id=family_id)

        first_items = (
            ("version-1", "doc-1", "chunk-1"),
            ("version-2", "doc-2", "chunk-2"),
        )
        second_items = (
            ("version-2", "doc-2", "chunk-2"),
            ("version-1", "doc-1", "chunk-1"),
        )
        for registry, admin, items in (
            (first_registry, first_admin, first_items),
            (second_registry, second_admin, second_items),
        ):
            for version_id, doc_id, chunk_id in items:
                add_version(registry, admin, doc_id=doc_id, version_id=version_id)
                add_chunk(
                    registry,
                    admin,
                    doc_id=doc_id,
                    version_id=version_id,
                    chunk_id=chunk_id,
                )
            registry.assign_split(admin, "family-1", "train")
            registry.assign_split(admin, "family-2", "validation")

        first = first_registry.build_snapshot(first_admin)
        second = second_registry.build_snapshot(second_admin)

        assert first.snapshot.manifest_sha256 == second.snapshot.manifest_sha256
        assert first.content_sha256 == second.content_sha256
        assert first.snapshot.split_lock_sha256 == second.snapshot.split_lock_sha256
        assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
        assert first.snapshot.snapshot_id == f"snap-{first.snapshot.manifest_sha256}"
    finally:
        first_registry.close()
        second_registry.close()


def test_content_and_split_hashes_change_independently(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1", version_id="version-1", chunk_id="chunk-1")
    registry.assign_split(admin, "family-1", "train")
    first = registry.build_snapshot(admin)

    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        chunk_id="chunk-2",
        chunk_index=1,
        text="The retention period is 45 days.",
    )
    second = registry.build_snapshot(admin)
    assert second.snapshot.manifest_sha256 != first.snapshot.manifest_sha256
    assert second.content_sha256 != first.content_sha256
    assert second.snapshot.split_lock_sha256 == first.snapshot.split_lock_sha256

    registry.assign_split(admin, "family-2", "test_ood_challenge")
    third = registry.build_snapshot(admin)
    assert third.content_sha256 == second.content_sha256
    assert third.snapshot.split_lock_sha256 != second.snapshot.split_lock_sha256


def test_snapshot_is_a_closed_set(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1", version_id="version-1", chunk_id="chunk-1")
    grant(registry, admin, doc_id="doc-1", roles=("corpus_admin",))
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        chunk_id="chunk-2",
        chunk_index=1,
        text="The retention period is 45 days.",
    )

    closed = registry.authorized_chunks(
        admin,
        as_of=AS_OF,
        snapshot_id=snapshot.snapshot.snapshot_id,
    )
    assert [chunk.chunk_id for chunk in closed] == ["chunk-1"]
    assert [chunk.chunk_id for chunk in registry.authorized_chunks(admin, as_of=AS_OF)] == [
        "chunk-1",
        "chunk-2",
    ]
    with pytest.raises(CorpusError) as raised:
        registry.get_authorized_chunk(
            admin,
            "chunk-2",
            as_of=AS_OF,
            snapshot_id=snapshot.snapshot.snapshot_id,
        )
    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND


def test_snapshot_rows_are_immutable(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    registry.assign_split(admin, "family-1", "train")
    registry.build_snapshot(admin)

    for statement in (
        "UPDATE snapshots SET index_version = 'changed'",
        "DELETE FROM snapshots",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            registry.connection.execute(statement)


def test_tampered_manifest_is_detected(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    registry.connection.execute("DROP TRIGGER snapshots_no_update")
    registry.connection.execute(
        "UPDATE snapshots SET manifest_json = ? WHERE snapshot_id = ?",
        ('{"manifest_version":"hallx-corpus-manifest-v1"}', snapshot.snapshot.snapshot_id),
    )
    with pytest.raises(CorpusError) as raised:
        registry.verify_snapshot(admin, snapshot.snapshot.snapshot_id)
    assert raised.value.code is CorpusErrorCode.SNAPSHOT_HASH_MISMATCH


def test_live_content_mismatch_is_detected(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    registry.connection.execute("DROP TRIGGER chunks_no_update")
    registry.connection.execute("UPDATE chunks SET canonical_sha256 = ?", ("0" * 64,))
    with pytest.raises(CorpusError) as raised:
        registry.verify_snapshot(admin, snapshot.snapshot.snapshot_id)
    assert raised.value.code is CorpusErrorCode.SNAPSHOT_HASH_MISMATCH


def test_snapshot_verify_succeeds(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    grant(registry, admin, doc_id="doc-1", roles=("corpus_admin",))
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    verified = registry.verify_snapshot(admin, snapshot.snapshot.snapshot_id)
    assert verified.snapshot.snapshot_id == snapshot.snapshot.snapshot_id
    assert verified.snapshot.document_hashes == {"doc-1": registry.get_document(admin, "doc-1").source_sha256}
    assert verified.snapshot.version_hashes == {"version-1": registry.get_version(admin, "doc-1", "version-1", as_of=AS_OF).content_sha256}
    assert verified.snapshot.chunk_hashes == {"chunk-1": registry.get_authorized_chunk(admin, "chunk-1", as_of=AS_OF).canonical_sha256}


def test_snapshot_requires_a_document(registry) -> None:
    admin = make_admin(registry)
    with pytest.raises(CorpusError) as raised:
        registry.build_snapshot(admin)
    assert raised.value.code is CorpusErrorCode.SNAPSHOT_INCOMPLETE
