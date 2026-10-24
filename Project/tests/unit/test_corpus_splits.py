import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from tests.support_corpus import (
    add_version,
    make_admin,
    register_document,
    registry_fixture,
    seed_chunk,
    sha,
)

registry = registry_fixture


def test_train_only_guard_allows_train_and_rejects_test(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1", version_id="version-1", chunk_id="chunk-1")
    seed_chunk(registry, admin, doc_id="doc-2", family_id="family-2", version_id="version-2", chunk_id="chunk-2")
    registry.assign_split(admin, "family-1", "train")
    registry.assign_split(admin, "family-2", "test_indomain")
    snapshot = registry.build_snapshot(admin)

    registry.require_train_only(snapshot.snapshot.snapshot_id, ("family-1",))
    with pytest.raises(CorpusError) as raised:
        registry.require_train_only(snapshot.snapshot.snapshot_id, ("family-2",))
    assert raised.value.code is CorpusErrorCode.SPLIT_FAMILY_LEAKAGE


def test_duplicate_source_across_splits_is_rejected(registry) -> None:
    admin = make_admin(registry)
    shared = sha("shared-source")
    register_document(registry, admin, doc_id="doc-1", family_id="family-1", source_sha256=shared)
    register_document(registry, admin, doc_id="doc-2", family_id="family-2", source_sha256=shared)
    add_version(registry, admin, doc_id="doc-1", version_id="version-1")
    add_version(registry, admin, doc_id="doc-2", version_id="version-2")
    registry.assign_split(admin, "family-1", "train")
    registry.assign_split(admin, "family-2", "test_ood_challenge")

    with pytest.raises(CorpusError) as raised:
        registry.build_snapshot(admin)
    assert raised.value.code is CorpusErrorCode.SPLIT_DUPLICATE_SOURCE


def test_snapshot_locks_split_assignment(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    registry.assign_split(admin, "family-1", "train")
    with pytest.raises(CorpusError) as raised:
        registry.assign_split(admin, "family-1", "validation")
    assert raised.value.code is CorpusErrorCode.SPLIT_LOCKED

    assert snapshot.snapshot.split_membership["train"] == ("family-1",)


def test_invalid_split_name_is_rejected(registry) -> None:
    admin = make_admin(registry)
    with pytest.raises(CorpusError) as raised:
        registry.assign_split(admin, "family-1", "holdout")
    assert raised.value.code is CorpusErrorCode.SPLIT_INVALID


def test_snapshot_requires_split_for_every_document(registry) -> None:
    admin = make_admin(registry)
    seed_chunk(registry, admin, doc_id="doc-1", family_id="family-1")

    with pytest.raises(CorpusError) as raised:
        registry.build_snapshot(admin)
    assert raised.value.code is CorpusErrorCode.SPLIT_INVALID


def test_snapshot_requires_an_activated_version(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1")
    registry.assign_split(admin, "family-1", "train")

    with pytest.raises(CorpusError) as raised:
        registry.build_snapshot(admin)
    assert raised.value.code is CorpusErrorCode.SNAPSHOT_INCOMPLETE
