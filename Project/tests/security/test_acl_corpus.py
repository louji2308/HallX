import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from hallx.models import DocumentStatus, Principal
from tests.support_corpus import (
    AS_OF,
    SENTINEL,
    add_chunk,
    add_version,
    audit_rows,
    grant,
    insert_foreign_principal,
    make_admin,
    make_user,
    register_document,
    registry_fixture,
)

registry = registry_fixture


def seed_private(registry, admin):
    register_document(registry, admin, doc_id="doc-1", family_id="family-1", title=SENTINEL)
    add_version(registry, admin, doc_id="doc-1", version_id="version-1", text=SENTINEL)
    add_chunk(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        chunk_id="chunk-1",
        text=SENTINEL,
    )


def test_content_is_denied_by_default(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)

    assert registry.list_documents(user) == ()
    assert registry.authorized_chunks(user, as_of=AS_OF) == ()
    decision = registry.authorize_chunk(user, "chunk-1", as_of=AS_OF)
    assert decision.allowed is False
    assert decision.reason_code == "ACL_DENIED"
    with pytest.raises(CorpusError) as raised:
        registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)
    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
    assert SENTINEL not in str(raised.value)


def test_revoked_acl_is_rechecked_on_source_open(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)
    grant(registry, admin, doc_id="doc-1")

    allowed = registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)
    assert allowed.chunk_id == "chunk-1"
    assert allowed.status is DocumentStatus.ACTIVE

    registry.revoke_acl(admin, "doc-1", ("analyst",))
    decision = registry.authorize_chunk(user, "chunk-1", as_of=AS_OF)
    assert decision.allowed is False
    assert decision.reason_code == "ACL_DENIED"
    with pytest.raises(CorpusError) as raised:
        registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)
    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
    with pytest.raises(CorpusError) as source_open:
        registry.get_version_text(user, "doc-1", "version-1")
    assert source_open.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
    assert registry.authorized_chunks(user, as_of=AS_OF) == ()
    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in str(source_open.value)


def test_cross_workspace_ids_are_uniformly_not_found(registry) -> None:
    admin = make_admin(registry)
    seed_private(registry, admin)
    insert_foreign_principal(
        registry,
        principal_id="other-user",
        tenant_id="tenant-b",
        roles=("analyst",),
    )
    other = Principal(principal_id="other-user", tenant_id="tenant-b", roles=("analyst",))

    decision = registry.authorize_chunk(other, "chunk-1", as_of=AS_OF)
    assert decision.allowed is False
    assert decision.reason_code == "NOT_FOUND"
    for call in (
        lambda: registry.get_authorized_chunk(other, "chunk-1", as_of=AS_OF),
        lambda: registry.get_document(other, "doc-1"),
        lambda: registry.get_version_text(other, "doc-1", "version-1"),
        lambda: registry.resolve_active_version(other, "doc-1", as_of=AS_OF),
    ):
        with pytest.raises(CorpusError) as raised:
            call()
        assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND
        assert SENTINEL not in str(raised.value)
    assert registry.list_documents(other) == ()


def test_admin_does_not_bypass_document_content_acl(registry) -> None:
    admin = make_admin(registry)
    seed_private(registry, admin)

    assert registry.authorize_chunk(admin, "chunk-1", as_of=AS_OF).reason_code == "ACL_DENIED"
    with pytest.raises(CorpusError):
        registry.get_authorized_chunk(admin, "chunk-1", as_of=AS_OF)
    with pytest.raises(CorpusError):
        registry.get_version_text(admin, "doc-1", "version-1")
    assert registry.authorized_chunks(admin, as_of=AS_OF) == ()
    assert registry.get_document(admin, "doc-1").doc_id == "doc-1"
    assert registry.list_documents(admin)[0].acl_roles == ()


def test_guessed_restricted_chunk_id_is_not_hydrated(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)

    decision = registry.authorize_chunk(user, "chunk-1", as_of=AS_OF)
    assert decision.allowed is False
    assert decision.reason_code == "ACL_DENIED"
    with pytest.raises(CorpusError) as raised:
        registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)
    assert SENTINEL not in str(raised.value)
    for row in audit_rows(registry):
        assert SENTINEL not in row["metadata_json"]


def test_forged_bundle_acl_cannot_override_live_acl(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)
    grant(registry, admin, doc_id="doc-1")
    previously_authorized = registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)
    assert previously_authorized.acl_roles == ("analyst",)

    registry.revoke_acl(admin, "doc-1", ("analyst",))
    with pytest.raises(CorpusError):
        registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)


def test_mutations_require_server_resolved_admin_role(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    forged = Principal(principal_id=user.principal_id, tenant_id="tenant-a", roles=("corpus_admin",))

    for actor in (user, forged):
        with pytest.raises(CorpusError) as raised:
            register_document(registry, actor, doc_id="forged-doc", family_id="family-1")
        assert raised.value.code is CorpusErrorCode.CORPUS_ROLE_REQUIRED


def test_acl_roles_are_redacted_for_non_admins(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)
    grant(registry, admin, doc_id="doc-1")

    assert registry.list_documents(user)[0].acl_roles == ()
    assert registry.list_documents(admin)[0].acl_roles == ("analyst",)


def test_reserved_and_empty_acl_roles_are_rejected(registry) -> None:
    admin = make_admin(registry)
    seed_private(registry, admin)

    for roles in ((), ("*",), ("public",), ("everyone",)):
        with pytest.raises(CorpusError):
            registry.grant_acl(admin, "doc-1", roles)


def test_non_admin_cannot_read_snapshot(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)
    grant(registry, admin, doc_id="doc-1")
    registry.assign_split(admin, "family-1", "train")
    snapshot = registry.build_snapshot(admin)

    with pytest.raises(CorpusError) as raised:
        registry.get_snapshot(user, snapshot.snapshot.snapshot_id)
    assert raised.value.code is CorpusErrorCode.CORPUS_ROLE_REQUIRED


def test_missing_and_restricted_chunks_have_the_same_public_error(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)

    errors = []
    for chunk_id in ("chunk-1", "does-not-exist"):
        with pytest.raises(CorpusError) as raised:
            registry.get_authorized_chunk(user, chunk_id, as_of=AS_OF)
        errors.append(str(raised.value))
    assert errors[0] == errors[1]


def test_acl_regrant_reauthorizes_source_open(registry) -> None:
    admin = make_admin(registry)
    user = make_user(registry, admin)
    seed_private(registry, admin)
    grant(registry, admin, doc_id="doc-1")

    registry.revoke_acl(admin, "doc-1", ("analyst",))
    with pytest.raises(CorpusError):
        registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF)

    grant(registry, admin, doc_id="doc-1")
    assert registry.get_authorized_chunk(user, "chunk-1", as_of=AS_OF).chunk_id == "chunk-1"


def test_snapshot_boundary_denials_are_audited(registry) -> None:
    admin = make_admin(registry)
    seed_private(registry, admin)
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
        text=SENTINEL,
    )

    assert (
        registry.authorize_chunk(
            admin,
            "chunk-2",
            as_of=AS_OF,
            snapshot_id=snapshot.snapshot.snapshot_id,
        ).reason_code
        == "NOT_IN_SNAPSHOT"
    )
    assert (
        registry.authorize_chunk(
            admin,
            "chunk-1",
            as_of=AS_OF,
            snapshot_id="snap-does-not-exist",
        ).reason_code
        == "NOT_FOUND"
    )
    reasons = [row["reason_code"] for row in audit_rows(registry)]
    assert "NOT_IN_SNAPSHOT" in reasons
    assert CorpusErrorCode.CORPUS_NOT_FOUND.value in reasons
