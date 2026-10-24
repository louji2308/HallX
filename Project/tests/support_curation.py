"""Fixtures and builders for P6 curation tests."""

from __future__ import annotations

from pathlib import Path

from hallx.curation import (
    CurationConfig,
    CurationTask,
    RunMode,
    SourceRecord,
    TrainingRecord,
    config_sha256,
    export_sha256,
    validate_export,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs" / "curation"
CONFIG_NAMES = ("qa", "cot", "adversarial-qa", "adversarial-preference", "grpo")
TASK_BY_NAME = {
    "qa": CurationTask.QA,
    "cot": CurationTask.COT,
    "adversarial-qa": CurationTask.ADVERSARIAL_QA,
    "adversarial-preference": CurationTask.ADVERSARIAL_PREFERENCE,
    "grpo": CurationTask.GRPO,
}

SNAPSHOT_ID = "snap-fixture-train-v1"
RUN_ID = "fixture-curation-qa-v1"
TOKENIZER_ID = "fixture/tokenizer-not-loaded-v1"
GENERATOR_ENDPOINT = "http://127.0.0.1:30000"
JUDGE_ENDPOINT = "http://127.0.0.1:30001"
GENERATOR_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
JUDGE_MODEL = "fixture/independent-judge"

TRAIN_TEXT = "The retention period is 30 days."
SECOND_TRAIN_TEXT = "The controller must notify the regulator within 72 hours."


def make_config(**overrides: object) -> CurationConfig:
    values: dict[str, object] = {
        "run_id": RUN_ID,
        "mode": RunMode.FIXTURE,
        "task": CurationTask.QA,
        "snapshot_id": SNAPSHOT_ID,
        "split_name": "train",
        "generator_endpoint": GENERATOR_ENDPOINT,
        "judge_endpoint": JUDGE_ENDPOINT,
        "generator_model": GENERATOR_MODEL,
        "judge_model": JUDGE_MODEL,
        "max_examples": 8,
        "max_tokens": 4096,
        "seed": 20261024,
        "expected_examples": 2,
        "expected_total_tokens": 100,
        "token_tolerance": 0.02,
        "tokenizer_id": TOKENIZER_ID,
        "output_path": "data/curation/fixture/train-qa.jsonl",
    }
    values.update(overrides)
    return CurationConfig(**values)


def construct_config(**overrides: object) -> CurationConfig:
    values = make_config().model_dump()
    values.update(overrides)
    return CurationConfig.model_construct(**values)


def make_source(
    source_id: str = "src-train-1",
    *,
    snapshot_id: str = SNAPSHOT_ID,
    family_id: str = "family-train-1",
    split: str = "train",
    chunk_id: str | None = None,
    canonical_text: str = TRAIN_TEXT,
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        snapshot_id=snapshot_id,
        family_id=family_id,
        split=split,
        chunk_id=chunk_id if chunk_id is not None else f"chunk-{source_id}",
        canonical_text=canonical_text,
    )


def make_sources() -> tuple[SourceRecord, ...]:
    return (
        make_source(),
        make_source(
            "src-train-2",
            family_id="family-train-2",
            canonical_text=SECOND_TRAIN_TEXT,
        ),
        make_source(
            "src-val-1",
            family_id="family-val-1",
            split="validation",
            canonical_text="Validation source text.",
        ),
        make_source(
            "src-test-1",
            family_id="family-test-1",
            split="test_indomain",
            canonical_text="In-domain test source text.",
        ),
        make_source(
            "src-ood-1",
            family_id="family-ood-1",
            split="test_ood_challenge",
            canonical_text="Out-of-domain test source text.",
        ),
    )


def leaky_sources() -> tuple[SourceRecord, ...]:
    return make_sources() + (
        make_source(
            "src-test-leak",
            family_id="family-train-1",
            split="test_indomain",
            canonical_text="A separate in-domain test source.",
        ),
    )


def make_record(
    config: CurationConfig | None = None,
    source: SourceRecord | None = None,
    **overrides: object,
) -> TrainingRecord:
    cfg = config if config is not None else make_config()
    src = source if source is not None else make_sources()[0]
    quote = str(overrides.get("quote", src.canonical_text))
    start = max(src.canonical_text.find(quote), 0)
    end = start + len(quote)
    if end <= start:
        end = start + 1
    values: dict[str, object] = {
        "sample_id": "sample-1",
        "run_id": cfg.run_id,
        "snapshot_id": cfg.snapshot_id,
        "config_sha256": config_sha256(cfg),
        "task": cfg.task,
        "source_id": src.source_id,
        "chunk_id": src.chunk_id,
        "prompt": "What is the retention period?",
        "completion": src.canonical_text,
        "quote": quote,
        "quote_start": start,
        "quote_end": end,
    }
    values.update(overrides)
    return TrainingRecord(**values)


def make_records(
    config: CurationConfig | None = None,
    sources: tuple[SourceRecord, ...] | None = None,
) -> tuple[TrainingRecord, TrainingRecord]:
    cfg = config if config is not None else make_config()
    pool = sources if sources is not None else make_sources()
    return (
        make_record(cfg, pool[0], sample_id="sample-1"),
        make_record(cfg, pool[1], sample_id="sample-2"),
    )


def valid_export() -> tuple[
    CurationConfig,
    tuple[TrainingRecord, TrainingRecord],
    tuple[SourceRecord, ...],
    int,
    str,
    str,
]:
    config = make_config()
    sources = make_sources()
    records = make_records(config, sources)
    return (
        config,
        records,
        sources,
        100,
        export_sha256(records),
        config.tokenizer_id,
    )


def run_export(
    config: CurationConfig,
    records: tuple[TrainingRecord, ...],
    sources: tuple[SourceRecord, ...],
    *,
    observed_total_tokens: int = 100,
    observed_sha256: str | None = None,
    observed_tokenizer_id: str | None = None,
):
    digest = export_sha256(records) if observed_sha256 is None else observed_sha256
    tokenizer = (
        config.tokenizer_id if observed_tokenizer_id is None else observed_tokenizer_id
    )
    return validate_export(
        config,
        records,
        sources,
        observed_total_tokens=observed_total_tokens,
        observed_sha256=digest,
        observed_tokenizer_id=tokenizer,
    )
