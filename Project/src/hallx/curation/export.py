"""Deterministic export hashing and provenance/quote/token gates."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable

from hallx.corpus.snapshot import canonical_json
from hallx.curation.config import config_sha256, validate_config, validate_split_manifest
from hallx.curation.models import (
    CurationConfig,
    CurationIssue,
    ExportValidation,
    IssueCode,
    SourceRecord,
    TrainingRecord,
)
from hallx.errors import SpanResolutionError
from hallx.validation.span import resolve_unique_quote

EXPORT_HASH_PREFIX = b"hallx.curation.export.v1\n"
_NON_TRAIN_SPLITS = frozenset({"validation", "test_indomain", "test_ood_challenge"})
_EMPTY_FIELDS = (
    "sample_id",
    "run_id",
    "snapshot_id",
    "source_id",
    "chunk_id",
    "prompt",
    "completion",
    "quote",
)


def export_sha256(records: Iterable[TrainingRecord]) -> str:
    materialized = tuple(records)
    lines = [
        canonical_json(record.model_dump(mode="json"))
        for record in sorted(materialized, key=lambda item: item.sample_id)
    ]
    payload = "\n".join(lines) + "\n"
    return hashlib.sha256(EXPORT_HASH_PREFIX + payload.encode("utf-8")).hexdigest()


def _issue(
    code: str,
    message: str,
    *,
    sample_id: str | None = None,
    source_id: str | None = None,
) -> CurationIssue:
    return CurationIssue(
        code=code,
        message=message,
        sample_id=sample_id,
        source_id=source_id,
    )


def _source_index(sources: Iterable[SourceRecord]) -> dict[str, SourceRecord]:
    index: dict[str, SourceRecord] = {}
    for source in sources:
        index.setdefault(source.source_id, source)
    return index


def _family_splits(sources: Iterable[SourceRecord]) -> dict[str, set[str]]:
    splits: dict[str, set[str]] = defaultdict(set)
    for source in sources:
        splits[source.family_id].add(source.split)
    return splits


def validate_export(
    config: CurationConfig,
    records: Iterable[TrainingRecord],
    sources: Iterable[SourceRecord],
    *,
    observed_total_tokens: int,
    observed_sha256: str,
    observed_tokenizer_id: str,
) -> ExportValidation:
    materialized = tuple(records)
    manifest = tuple(sources)
    issues: list[CurationIssue] = []
    issues.extend(validate_split_manifest(manifest))
    issues.extend(validate_config(config))

    try:
        expected_config_sha = config_sha256(config)
    except ValueError:
        expected_config_sha = None

    index = _source_index(manifest)
    family_splits = _family_splits(manifest)
    seen_samples: set[str] = set()

    for record in materialized:
        for field_name in _EMPTY_FIELDS:
            if getattr(record, field_name).strip() == "":
                issues.append(
                    _issue(
                        IssueCode.EMPTY_FIELD,
                        f"{field_name} must be non-empty",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )

        source = index.get(record.source_id)
        if source is None:
            issues.append(
                _issue(
                    IssueCode.UNKNOWN_SOURCE,
                    "training record references an unknown source",
                    sample_id=record.sample_id or None,
                    source_id=record.source_id or None,
                )
            )
        else:
            if (
                record.snapshot_id != config.snapshot_id
                or source.snapshot_id != config.snapshot_id
            ):
                issues.append(
                    _issue(
                        IssueCode.SNAPSHOT_MISMATCH,
                        "record or source snapshot does not match the config snapshot",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if source.split != "train":
                issues.append(
                    _issue(
                        IssueCode.SPLIT_LEAKAGE,
                        "source is not in the train split",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            elif family_splits[source.family_id] & _NON_TRAIN_SPLITS:
                issues.append(
                    _issue(
                        IssueCode.SPLIT_LEAKAGE,
                        "source family also appears in validation, test, or OOD",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if record.run_id != config.run_id:
                issues.append(
                    _issue(
                        IssueCode.RUN_MISMATCH,
                        "record run_id does not match the config run_id",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if record.task != config.task:
                issues.append(
                    _issue(
                        IssueCode.TASK_MISMATCH,
                        "record task does not match the config task",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if record.chunk_id != source.chunk_id:
                issues.append(
                    _issue(
                        IssueCode.CHUNK_MISMATCH,
                        "record chunk_id does not match the source chunk_id",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if expected_config_sha is not None and record.config_sha256 != expected_config_sha:
                issues.append(
                    _issue(
                        IssueCode.CONFIG_MISMATCH,
                        "record config_sha256 does not match the config",
                        sample_id=record.sample_id or None,
                        source_id=record.source_id or None,
                    )
                )
            if record.quote.strip() != "":
                try:
                    expected_span = resolve_unique_quote(source.canonical_text, record.quote)
                except SpanResolutionError:
                    issues.append(
                        _issue(
                            IssueCode.QUOTE_UNMAPPABLE,
                            "quote is absent or occurs more than once in the source",
                            sample_id=record.sample_id or None,
                            source_id=record.source_id or None,
                        )
                    )
                else:
                    if expected_span != (record.quote_start, record.quote_end):
                        issues.append(
                            _issue(
                                IssueCode.QUOTE_SPAN_MISMATCH,
                                "quote offsets are not the server-computed span",
                                sample_id=record.sample_id or None,
                                source_id=record.source_id or None,
                            )
                        )

        if record.sample_id.strip() != "":
            if record.sample_id in seen_samples:
                issues.append(
                    _issue(
                        IssueCode.DUPLICATE_SAMPLE,
                        "sample_id appears more than once in the export",
                        sample_id=record.sample_id,
                        source_id=record.source_id or None,
                    )
                )
            else:
                seen_samples.add(record.sample_id)

    observed_examples = len(materialized)
    if observed_examples != config.expected_examples:
        issues.append(
            _issue(
                IssueCode.EXAMPLE_COUNT_MISMATCH,
                f"observed {observed_examples} examples, expected {config.expected_examples}",
            )
        )
    if observed_tokenizer_id != config.tokenizer_id:
        issues.append(
            _issue(
                IssueCode.TOKENIZER_MISMATCH,
                "observed tokenizer_id does not match the config tokenizer_id",
            )
        )
    denominator = max(config.expected_total_tokens, 1)
    if (
        abs(observed_total_tokens - config.expected_total_tokens) / denominator
        > config.token_tolerance
    ):
        issues.append(
            _issue(
                IssueCode.TOKEN_PARITY_FAILED,
                "observed token count is outside the configured tolerance",
            )
        )

    computed_sha256 = export_sha256(materialized)
    if observed_sha256 != computed_sha256:
        issues.append(
            _issue(
                IssueCode.CHECKSUM_MISMATCH,
                "observed export checksum does not match the canonical export digest",
            )
        )

    return ExportValidation(
        passed=not issues,
        issues=tuple(issues),
        computed_sha256=computed_sha256,
        observed_examples=observed_examples,
        observed_total_tokens=observed_total_tokens,
    )
