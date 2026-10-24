"""Loopback-only SGLang-compatible inference adapter."""

from hallx.inference.models import (
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
    HealthStatus,
    InferenceError,
    InferenceErrorCode,
)
from hallx.inference.sglang import SGLangClient

__all__ = [
    "ChatMessage",
    "GenerationRequest",
    "GenerationResponse",
    "HealthStatus",
    "InferenceError",
    "InferenceErrorCode",
    "SGLangClient",
]
