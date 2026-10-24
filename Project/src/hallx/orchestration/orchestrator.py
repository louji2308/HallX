"""Bounded orchestration from a frozen evidence bundle to validated output."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from typing import Any, Protocol

from hallx.errors import ErrorCode, ValidationIssue, issue
from hallx.inference.models import (
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
)
from hallx.models import (
    EvidenceBundle,
    EvidenceState,
    Principal,
    ValidationOutcome,
    ValidationResult,
)
from hallx.orchestration.models import GenerationAttempt, OrchestrationResult
from hallx.prompting import PromptPayload, build_prompt
from hallx.validation import EntailmentVerifier, validate_envelope, validate_evidence_bundle


class GeneratorProtocol(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


class Orchestrator:
    def __init__(
        self,
        generator: GeneratorProtocol,
        *,
        schema: dict,
        max_repairs: int = 1,
    ) -> None:
        if isinstance(max_repairs, bool) or not isinstance(max_repairs, int):
            raise TypeError("max_repairs must be an integer")
        if max_repairs not in (0, 1):
            raise ValueError("max_repairs must be 0 or 1")
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dictionary")

        self._generator = generator
        self._schema = deepcopy(schema)
        self.max_repairs = max_repairs

    def answer(
        self,
        question: str,
        bundle: EvidenceBundle,
        principal: Principal,
        *,
        as_of: date,
        entailment: EntailmentVerifier | None,
    ) -> OrchestrationResult:
        bundle_issues = validate_evidence_bundle(bundle, principal)
        if any(item.blocking for item in bundle_issues):
            validation = _bundle_rejection(bundle_issues)
            return _rejected_result(validation=validation, attempts=(), repairs_used=0)

        prompt = build_prompt(question, bundle, schema=self._schema)
        request = self._request_from_prompt(prompt)
        attempts: list[GenerationAttempt] = []

        response = self._generator.generate(request)
        outcome = self._validate_raw(
            response.raw_text,
            bundle=bundle,
            principal=principal,
            as_of=as_of,
            entailment=entailment,
            previous_repairs=0,
        )
        attempts.append(_attempt(0, response, outcome.result))
        if outcome.accepted:
            return _accepted_result(validation=outcome, attempts=tuple(attempts), repairs_used=0)

        if not outcome.result.repair_allowed or self.max_repairs == 0:
            return _rejected_result(
                validation=outcome.result,
                attempts=tuple(attempts),
                repairs_used=0,
            )

        repair_request = self._repair_request(request, outcome.result)
        repaired_response = self._generator.generate(repair_request)
        repaired_outcome = self._validate_raw(
            repaired_response.raw_text,
            bundle=bundle,
            principal=principal,
            as_of=as_of,
            entailment=entailment,
            previous_repairs=1,
        )
        attempts.append(_attempt(1, repaired_response, repaired_outcome.result))
        if repaired_outcome.accepted:
            return _accepted_result(
                validation=repaired_outcome,
                attempts=tuple(attempts),
                repairs_used=1,
            )
        return _rejected_result(
            validation=repaired_outcome.result,
            attempts=tuple(attempts),
            repairs_used=1,
        )

    def _request_from_prompt(self, prompt: PromptPayload) -> GenerationRequest:
        return GenerationRequest(
            messages=(
                ChatMessage(role="system", content=prompt.system_prompt),
                ChatMessage(role="user", content=prompt.user_prompt),
            ),
            response_schema=prompt.response_schema,
        )

    def _repair_request(
        self,
        original: GenerationRequest,
        validation: ValidationResult,
    ) -> GenerationRequest:
        issues = [
            {
                "code": item.code.value,
                "severity": item.severity.value,
                "message": item.message,
                "chunk_id": item.chunk_id,
                "claim_index": item.claim_index,
            }
            for item in validation.issues
        ]
        repair_context = json.dumps(
            {"repair_round": 1, "validation_issues": issues},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        repair_suffix = (
            "\n\nREPAIR REQUEST\n"
            "The previous candidate failed server validation. Return a corrected and complete "
            "JSON object that conforms to the response schema. Use only the source IDs in the "
            "evidence above and do not add commentary.\n"
            f"REPAIR_CONTEXT_JSON:\n{repair_context}"
        )
        messages = original.messages[:-1] + (
            ChatMessage(role="user", content=original.messages[-1].content + repair_suffix),
        )
        return GenerationRequest(
            messages=messages,
            response_schema=original.response_schema,
            temperature=original.temperature,
            seed=original.seed,
            max_tokens=original.max_tokens,
        )

    def _validate_raw(
        self,
        raw_text: str,
        *,
        bundle: EvidenceBundle,
        principal: Principal,
        as_of: date,
        entailment: EntailmentVerifier | None,
        previous_repairs: int,
    ) -> ValidationOutcome:
        try:
            candidate: Any = json.loads(raw_text)
        except (json.JSONDecodeError, RecursionError):
            validation = ValidationResult(
                accepted=False,
                final_state=None,
                model_state=EvidenceState.MISSING,
                model_state_matches=False,
                issues=(
                    issue(
                        ErrorCode.SCHEMA_INVALID,
                        "candidate is not valid JSON",
                    ),
                ),
                repair_allowed=False,
                final_human_review_required=True,
            )
            return ValidationOutcome(accepted=False, envelope=None, result=validation)

        return validate_envelope(
            candidate,
            bundle,
            principal,
            as_of=as_of,
            previous_repairs=previous_repairs,
            entailment=entailment,
        )


def _bundle_rejection(bundle_issues: tuple[ValidationIssue, ...]) -> ValidationResult:
    return ValidationResult(
        accepted=False,
        final_state=None,
        model_state=EvidenceState.MISSING,
        model_state_matches=False,
        issues=bundle_issues,
        repair_allowed=False,
        final_human_review_required=True,
    )


def _attempt(
    index: int,
    response: GenerationResponse,
    validation: ValidationResult,
) -> GenerationAttempt:
    return GenerationAttempt(
        attempt_index=index,
        request_id=response.request_id,
        raw_text=response.raw_text,
        validation=validation,
        elapsed_ms=response.elapsed_ms,
    )


def _accepted_result(
    *,
    validation: ValidationOutcome,
    attempts: tuple[GenerationAttempt, ...],
    repairs_used: int,
) -> OrchestrationResult:
    if validation.envelope is None or validation.result.final_state is None:
        raise RuntimeError("accepted validation outcome is internally inconsistent")
    return OrchestrationResult(
        accepted=True,
        envelope=validation.envelope,
        validation=validation.result,
        attempts=attempts,
        repairs_used=repairs_used,
        final_state=validation.result.final_state,
    )


def _rejected_result(
    *,
    validation: ValidationResult,
    attempts: tuple[GenerationAttempt, ...],
    repairs_used: int,
) -> OrchestrationResult:
    return OrchestrationResult(
        accepted=False,
        envelope=None,
        validation=validation,
        attempts=attempts,
        repairs_used=repairs_used,
        final_state=EvidenceState.MISSING,
    )
