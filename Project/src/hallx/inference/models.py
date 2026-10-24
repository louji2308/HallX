"""Typed models and failures for the loopback inference adapter."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())


class ChatMessage(StrictModel):
    role: Literal["system", "user"]
    content: str


class GenerationRequest(StrictModel):
    messages: tuple[ChatMessage, ...]
    response_schema: dict
    temperature: float = 0.0
    seed: int = 42
    max_tokens: int = 2048


class GenerationResponse(StrictModel):
    raw_text: str
    model_id: str
    adapter_id: str | None = None
    request_id: str
    finish_reason: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    elapsed_ms: float = Field(ge=0)


class HealthStatus(StrictModel):
    healthy: bool
    model_id: str | None = None
    detail: str | None = None


class InferenceErrorCode(str, Enum):
    NON_LOOPBACK_ENDPOINT = "NON_LOOPBACK_ENDPOINT"
    HEALTH_FAILED = "HEALTH_FAILED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    NO_FALLBACK = "NO_FALLBACK"


class InferenceError(Exception):
    """A typed, fail-closed adapter failure with a bounded detail string."""

    def __init__(self, code: InferenceErrorCode, detail: str) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail
