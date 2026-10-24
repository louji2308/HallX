from hallx.curation import (
    CurationTask,
    IssueCode,
    export_sha256,
    validate_export,
)
from tests.support_curation import (
    TRAIN_TEXT,
    leaky_sources,
    make_config,
    make_record,
    make_records,
    make_source,
    make_sources,
    run_export,
    valid_export,
)


def _codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


def test_curation_valid_fixture_passes() -> None:
    config, records, sources, tokens, digest, tokenizer = valid_export()
    result = validate_export(
        config,
        records,
        sources,
        observed_total_tokens=tokens,
        observed_sha256=digest,
        observed_tokenizer_id=tokenizer,
    )
    assert result.passed
    assert result.issues == ()
    assert result.computed_sha256 == digest
    assert result.observed_examples == 2
    assert result.observed_total_tokens == tokens


def test_curation_rejects_test_ood_leakage() -> None:
    config = make_config()
    sources = make_sources()
    records = make_records(config, sources)

    incomplete = run_export(config, records, (sources[0], sources[1]))
    assert _codes(incomplete) == [IssueCode.SPLIT_MANIFEST_INCOMPLETE] * 3

    for split_index in (3, 4):
        tangled = (
            make_record(config, sources[0], sample_id="sample-1"),
            make_record(config, sources[split_index], sample_id="sample-2"),
        )
        result = run_export(config, tangled, sources)
        assert _codes(result) == [IssueCode.SPLIT_LEAKAGE]

    family_leak = run_export(config, records, leaky_sources())
    assert _codes(family_leak) == [IssueCode.SPLIT_LEAKAGE]


def test_curation_quote_must_be_unique_and_server_computed() -> None:
    config = make_config()
    base = make_sources()

    ambiguous = make_source(
        "src-ambiguous",
        family_id="family-train-ambiguous",
        canonical_text="The period is 30 days. The period is 30 days.",
    )
    overlapping = make_source(
        "src-overlap",
        family_id="family-train-overlap",
        canonical_text="aaa",
    )
    missing = make_source(
        "src-missing-quote",
        family_id="family-train-missing",
        canonical_text="A unique sentence.",
    )
    sources = base + (ambiguous, overlapping, missing)

    cases = (
        (ambiguous, {"quote": "The period is 30 days."}),
        (overlapping, {"quote": "aa"}),
        (missing, {"quote": "zzz"}),
    )
    for source, overrides in cases:
        records = (
            make_record(config, base[0], sample_id="sample-1"),
            make_record(config, source, sample_id="sample-2", **overrides),
        )
        result = run_export(config, records, sources)
        assert _codes(result) == [IssueCode.QUOTE_UNMAPPABLE]

    wrong_span = (
        make_record(config, base[0], sample_id="sample-1"),
        make_record(
            config,
            base[1],
            sample_id="sample-2",
            quote_start=1,
            quote_end=len(TRAIN_TEXT),
        ),
    )
    result = run_export(config, wrong_span, base)
    assert _codes(result) == [IssueCode.QUOTE_SPAN_MISMATCH]


def test_curation_provenance_identity_failures() -> None:
    config = make_config()
    sources = make_sources()
    baseline = make_records(config, sources)

    def codes_with(overrides: dict[str, object], source=None) -> list[str]:
        target = source if source is not None else sources[0]
        sample = {"sample_id": "sample-1", **overrides}
        records = (
            make_record(config, target, **sample),
            baseline[1],
        )
        pool = sources if source is None else sources + (source,)
        return _codes(run_export(config, records, pool))

    assert codes_with({"run_id": "other-run"}) == [IssueCode.RUN_MISMATCH]
    assert codes_with({"snapshot_id": "snap-other"}) == [IssueCode.SNAPSHOT_MISMATCH]
    assert codes_with({"task": CurationTask.COT}) == [IssueCode.TASK_MISMATCH]
    assert codes_with({"chunk_id": "chunk-other"}) == [IssueCode.CHUNK_MISMATCH]
    assert codes_with({"config_sha256": "f" * 64}) == [IssueCode.CONFIG_MISMATCH]
    assert codes_with({"source_id": "src-missing"}) == [IssueCode.UNKNOWN_SOURCE]
    assert codes_with({"prompt": ""}) == [IssueCode.EMPTY_FIELD]
    assert codes_with({"sample_id": ""}) == [IssueCode.EMPTY_FIELD]
    assert codes_with({"quote": "", "quote_start": 0, "quote_end": 1}) == [
        IssueCode.EMPTY_FIELD
    ]

    other_snapshot = make_source(
        "src-other-snapshot",
        snapshot_id="snap-other",
        family_id="family-train-other-snapshot",
    )
    assert codes_with({}, source=other_snapshot) == [IssueCode.SNAPSHOT_MISMATCH]


def test_curation_rejects_duplicates() -> None:
    config = make_config()
    sources = make_sources()
    records = make_records(config, sources)

    duplicate_sample = (
        records[0],
        make_record(config, sources[1], sample_id="sample-1"),
    )
    result = run_export(config, duplicate_sample, sources)
    assert _codes(result) == [IssueCode.DUPLICATE_SAMPLE]

    result = run_export(config, records, sources + (sources[0],))
    assert _codes(result) == [IssueCode.DUPLICATE_SOURCE]


def test_curation_export_gate_failures() -> None:
    config = make_config()
    sources = make_sources()
    records = make_records(config, sources)

    count_config = make_config(expected_examples=3)
    count_records = make_records(count_config, sources)
    assert _codes(run_export(count_config, count_records, sources)) == [
        IssueCode.EXAMPLE_COUNT_MISMATCH
    ]

    result = run_export(
        config,
        records,
        sources,
        observed_tokenizer_id="fixture/other-tokenizer",
    )
    assert _codes(result) == [IssueCode.TOKENIZER_MISMATCH]

    result = run_export(config, records, sources, observed_total_tokens=103)
    assert _codes(result) == [IssueCode.TOKEN_PARITY_FAILED]

    boundary = run_export(config, records, sources, observed_total_tokens=102)
    assert boundary.passed

    result = run_export(config, records, sources, observed_sha256="0" * 64)
    assert _codes(result) == [IssueCode.CHECKSUM_MISMATCH]

    zero_config = make_config(expected_total_tokens=0)
    zero_records = make_records(zero_config, sources)
    assert run_export(
        zero_config,
        zero_records,
        sources,
        observed_total_tokens=0,
    ).passed


def test_curation_issue_order_is_deterministic() -> None:
    config = make_config()
    sources = make_sources()
    records = (
        make_record(
            config,
            sources[0],
            sample_id="sample-1",
            prompt="",
            run_id="other-run",
            quote_start=1,
        ),
        make_record(config, sources[1], sample_id="sample-2"),
    )
    first = run_export(config, records, sources)
    second = run_export(config, records, sources)

    assert first.issues == second.issues
    assert [issue.code for issue in first.issues] == [
        IssueCode.EMPTY_FIELD,
        IssueCode.RUN_MISMATCH,
        IssueCode.QUOTE_SPAN_MISMATCH,
    ]
    assert export_sha256(records) == first.computed_sha256
