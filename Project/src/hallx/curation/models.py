"""Frozen P6 curation models and machine-readable issue codes."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_HEX64 = r"^[0-9a-f]{64}$"


class CurationTask(str, Enum):
    QA = "qa"
    COT = "cot"
    ADVERSARIAL_QA = "adversarial_qa"
    ADVERSARIAL_PREFERENCE = "adversarial_preference"
    GRPO = "grpo"


class RunMode(str, Enum):
    FIXTURE = "fixture"
    LIVE = "live"


class IssueCode:
    SPLIT_NOT_TRAIN = "SPLIT_NOT_TRAIN"
    NON_LOOPBACK_ENDPOINT = "NON_LOOPBACK_ENDPOINT"
    GEN_JUDGE_SAME_ENDPOINT = "GEN_JUDGE_SAME_ENDPOINT"
    GEN_JUDGE_SAME_MODEL = "GEN_JUDGE_SAME_MODEL"
    INVALID_BUDGET = "INVALID_BUDGET"
    SPLIT_MANIFEST_INCOMPLETE = "SPLIT_MANIFEST_INCOMPLETE"
    DUPLICATE_SOURCE = "DUPLICATE_SOURCE"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    SPLIT_LEAKAGE = "SPLIT_LEAKAGE"
    RUN_MISMATCH = "RUN_MISMATCH"
    TASK_MISMATCH = "TASK_MISMATCH"
    CHUNK_MISMATCH = "CHUNK_MISMATCH"
    CONFIG_MISMATCH = "CONFIG_MISMATCH"
    EMPTY_FIELD = "EMPTY_FIELD"
    DUPLICATE_SAMPLE = "DUPLICATE_SAMPLE"
    QUOTE_UNMAPPABLE = "QUOTE_UNMAPPABLE"
    QUOTE_SPAN_MISMATCH = "QUOTE_SPAN_MISMATCH"
    EXAMPLE_COUNT_MISMATCH = "EXAMPLE_COUNT_MISMATCH"
    TOKENIZER_MISMATCH = "TOKENIZER_MISMATCH"
    TOKEN_PARITY_FAILED = "TOKEN_PARITY_FAILED"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class CurationConfig(_Strict):
    run_id: str = Field(min_length=1)
    mode: RunMode
    task: CurationTask
    snapshot_id: str = Field(min_length=1)
    split_name: str
    generator_endpoint: str = Field(min_length=1)
    judge_endpoint: str = Field(min_length=1)
    generator_model: str = Field(min_length=1)
    judge_model: str = Field(min_length=1)
    max_examples: int = Field(gt=0)
    max_tokens: int = Field(gt=0)
    seed: int
    expected_examples: int = Field(gt=0)
    expected_total_tokens: int = Field(ge=0)
    token_tolerance: float = 0.02
    tokenizer_id: str = Field(min_length=1)
    output_path: str = Field(min_length=1)


class SourceRecord(_Strict):
    source_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    split: Literal["train", "validation", "test_indomain", "test_ood_challenge"]
    chunk_id: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)


class TrainingRecord(_Strict):
    sample_id: str
    run_id: str
    snapshot_id: str
    config_sha256: str = Field(pattern=_HEX64)
    task: CurationTask
    source_id: str
    chunk_id: str
    prompt: str
    completion: str
    quote: str
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)

    @model_validator(mode="after")
    def _require_ordered_span(self) -> TrainingRecord:
        if self.quote_end <= self.quote_start:
            raise ValueError("quote_end must be greater than quote_start")
        return self


class CurationIssue(_Strict):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    sample_id: str | None = None
    source_id: str | None = None


class ExportValidation(_Strict):
    passed: bool
    issues: tuple[CurationIssue, ...]
    computed_sha256: str = Field(pattern=_HEX64)
    observed_examples: int = Field(ge=0)
    observed_total_tokens: int
