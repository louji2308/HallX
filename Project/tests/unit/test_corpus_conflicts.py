from datetime import date

import pytest

from hallx.corpus import CorpusError, CorpusErrorCode
from tests.support_corpus import (
    AS_OF,
    add_version,
    grant,
    make_admin,
    register_document,
    registry_fixture,
)

registry = registry_fixture


def seed_pair(registry, admin):
    register_document(registry, admin, doc_id="doc-1", family_id="family-1", authority="policy")
    register_document(registry, admin, doc_id="doc-2", family_id="family-2", authority="statute")
    add_version(registry, admin, doc_id="doc-1", version_id="version-1", text="The limit is 30 days.")
    add_version(registry, admin, doc_id="doc-2", version_id="version-2", text="The limit is 60 days.")
    grant(registry, admin, doc_id="doc-1", roles=("corpus_admin",))
    grant(registry, admin, doc_id="doc-2", roles=("corpus_admin",))


def test_active_pair_without_rule_is_unresolved(registry) -> None:
    admin = make_admin(registry)
    seed_pair(registry, admin)

    result = registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert result.status == "UNRESOLVED"
    assert result.winner_version_id is None


def test_authority_alone_does_not_resolve(registry) -> None:
    admin = make_admin(registry)
    seed_pair(registry, admin)

    result = registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert result.status == "UNRESOLVED"


def test_explicit_precedence_rule_resolves_pair(registry) -> None:
    admin = make_admin(registry)
    seed_pair(registry, admin)
    registry.add_precedence_rule(
        admin,
        rule_id="rule-1",
        winner_version_id="version-2",
        loser_version_id="version-1",
        reason="Newer statutory source",
    )

    result = registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert result.status == "RESOLVED"
    assert result.winner_version_id == "version-2"
    assert result.rule_ids == ("rule-1",)


def test_opposite_rules_are_ambiguous(registry) -> None:
    admin = make_admin(registry)
    seed_pair(registry, admin)
    registry.add_precedence_rule(
        admin,
        rule_id="rule-1",
        winner_version_id="version-1",
        loser_version_id="version-2",
        reason="Policy wins",
    )
    registry.add_precedence_rule(
        admin,
        rule_id="rule-2",
        winner_version_id="version-2",
        loser_version_id="version-1",
        reason="Statute wins",
    )

    result = registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert result.status == "AMBIGUOUS"
    assert result.rule_ids == ("rule-1", "rule-2")


def test_stale_pair_is_not_a_conflict(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1")
    register_document(registry, admin, doc_id="doc-2", family_id="family-2")
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        effective_from=date(2026, 1, 1),
        effective_until=date(2026, 6, 1),
    )
    add_version(registry, admin, doc_id="doc-2", version_id="version-2")
    grant(registry, admin, doc_id="doc-1", roles=("corpus_admin",))
    grant(registry, admin, doc_id="doc-2", roles=("corpus_admin",))

    result = registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert result.status == "NOT_A_CONFLICT"


def test_conflict_requires_access_to_both_documents(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin, doc_id="doc-1", family_id="family-1")
    register_document(registry, admin, doc_id="doc-2", family_id="family-2")
    add_version(registry, admin, doc_id="doc-1", version_id="version-1")
    add_version(registry, admin, doc_id="doc-2", version_id="version-2")
    grant(registry, admin, doc_id="doc-1", roles=("corpus_admin",))

    with pytest.raises(CorpusError) as raised:
        registry.resolve_version_conflict(admin, "version-1", "version-2", as_of=AS_OF)
    assert raised.value.code is CorpusErrorCode.CORPUS_NOT_FOUND


def test_conflict_pair_must_be_distinct(registry) -> None:
    admin = make_admin(registry)
    register_document(registry, admin)
    add_version(registry, admin)
    with pytest.raises(CorpusError) as raised:
        registry.resolve_version_conflict(admin, "version-1", "version-1", as_of=AS_OF)
    assert raised.value.code is CorpusErrorCode.CONFLICT_INVALID
