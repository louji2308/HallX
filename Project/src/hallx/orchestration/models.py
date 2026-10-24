"""Frozen orchestration result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hallx.models import (
    EvidenceState,
    ValidatedProofEnvelope,
    ValidationResult,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationAttempt(StrictModel):
    attempt_index: int = Field(ge=0)
    request_id: str
    raw_text: str
    validation: ValidationResult
    elapsed_ms: float = Field(ge=0)


class OrchestrationResult(StrictModel):
    accepted: bool
    envelope: ValidatedProofEnvelope | None
    validation: ValidationResult
    attempts: tuple[GenerationAttempt, ...]
    repairs_used: int = Field(ge=0, le=1)
    final_state: EvidenceState

    @model_validator(mode="after")
    def _consistent(self) -> OrchestrationResult:
        if self.accepted != self.validation.accepted:
            raise ValueError("orchestration acceptance must match validation acceptance")
        if self.accepted:
            if self.envelope is None:
                raise ValueError("an accepted result requires a validated envelope")
            if self.validation.final_state is None:
                raise ValueError("an accepted result requires a final validation state")
            if self.final_state != self.validation.final_state:
                raise ValueError("final state must come from the validation result")
        else:
            if self.envelope is not None:
                raise ValueError("a rejected result must not expose an envelope")
            if self.final_state is not EvidenceState.MISSING:
                raise ValueError("a rejected result must fail closed as MISSING")
        return self
