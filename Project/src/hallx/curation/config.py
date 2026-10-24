"""Curation configuration loading, identity hashing, and validation."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from pathlib import Path

from hallx.corpus.snapshot import canonical_json
from hallx.curation.endpoints import endpoint_identity, model_identity
from hallx.curation.models import (
    CurationConfig,
    CurationIssue,
    IssueCode,
    SourceRecord,
)

CONFIG_HASH_PREFIX = b"hallx.curation.config.v1\n"
SPLIT_NAMES = ("train", "validation", "test_indomain", "test_ood_challenge")


def load_config(path: str | Path) -> CurationConfig:
    return CurationConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def config_sha256(config: CurationConfig) -> str:
    payload = canonical_json(config.model_dump(mode="json"))
    return hashlib.sha256(CONFIG_HASH_PREFIX + payload.encode("utf-8")).hexdigest()


def _issue(code: str, message: str) -> CurationIssue:
    return CurationIssue(code=code, message=message)


def validate_config(config: CurationConfig) -> tuple[CurationIssue, ...]:
    issues: list[CurationIssue] = []
    generator = endpoint_identity(config.generator_endpoint)
    judge = endpoint_identity(config.judge_endpoint)
    if generator is None:
        issues.append(
            _issue(
                IssueCode.NON_LOOPBACK_ENDPOINT,
                "generator_endpoint must be an explicit loopback HTTP endpoint",
            )
        )
    if judge is None:
        issues.append(
            _issue(
                IssueCode.NON_LOOPBACK_ENDPOINT,
                "judge_endpoint must be an explicit loopback HTTP endpoint",
            )
        )
    if generator is not None and judge is not None and generator == judge:
        issues.append(
            _issue(
                IssueCode.GEN_JUDGE_SAME_ENDPOINT,
                "generator and judge must use different loopback ports",
            )
        )
    if model_identity(config.generator_model) == model_identity(config.judge_model):
        issues.append(
            _issue(
                IssueCode.GEN_JUDGE_SAME_MODEL,
                "generator and judge model IDs must differ",
            )
        )
    if config.split_name != "train":
        issues.append(
            _issue(
                IssueCode.SPLIT_NOT_TRAIN,
                "curation configs may only target the train split",
            )
        )
    if config.max_examples <= 0:
        issues.append(_issue(IssueCode.INVALID_BUDGET, "max_examples must be positive"))
    if config.max_tokens <= 0:
        issues.append(_issue(IssueCode.INVALID_BUDGET, "max_tokens must be positive"))
    if config.expected_examples <= 0:
        issues.append(_issue(IssueCode.INVALID_BUDGET, "expected_examples must be positive"))
    if config.expected_total_tokens < 0:
        issues.append(
            _issue(IssueCode.INVALID_BUDGET, "expected_total_tokens must be non-negative")
        )
    if not math.isfinite(config.token_tolerance) or not 0.0 <= config.token_tolerance <= 1.0:
        issues.append(
            _issue(IssueCode.INVALID_BUDGET, "token_tolerance must be finite and within [0, 1]")
        )
    if config.expected_examples > config.max_examples:
        issues.append(
            _issue(IssueCode.INVALID_BUDGET, "expected_examples exceeds max_examples")
        )
    if config.expected_total_tokens > config.max_examples * config.max_tokens:
        issues.append(
            _issue(
                IssueCode.INVALID_BUDGET,
                "expected_total_tokens exceeds max_examples * max_tokens",
            )
        )
    return tuple(issues)


def validate_split_manifest(
    sources: Iterable[SourceRecord],
) -> tuple[CurationIssue, ...]:
    records = tuple(sources)
    issues: list[CurationIssue] = []
    present = {record.split for record in records}
    for split_name in SPLIT_NAMES:
        if split_name not in present:
            issues.append(
                _issue(
                    IssueCode.SPLIT_MANIFEST_INCOMPLETE,
                    f"split manifest has no source in {split_name}",
                )
            )
    seen: set[str] = set()
    for record in records:
        if record.source_id in seen:
            issues.append(
                CurationIssue(
                    code=IssueCode.DUPLICATE_SOURCE,
                    message="source_id appears more than once in the split manifest",
                    source_id=record.source_id,
                )
            )
        else:
            seen.add(record.source_id)
    return tuple(issues)
