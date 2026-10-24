"""Loopback-only SGLang-compatible HTTP client with a single request attempt."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from http.client import HTTPConnection, HTTPException
from typing import Any
from urllib.parse import urlsplit

from hallx.inference.models import (
    GenerationRequest,
    GenerationResponse,
    HealthStatus,
    InferenceError,
    InferenceErrorCode,
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_CHAT_PATH = "/v1/chat/completions"
_MODELS_PATH = "/v1/models"


def _reject_endpoint(detail: str) -> InferenceError:
    return InferenceError(InferenceErrorCode.NON_LOOPBACK_ENDPOINT, detail)


def _canonical_base_url(base_url: str) -> tuple[str, str, int]:
    if not isinstance(base_url, str) or not base_url:
        raise _reject_endpoint("base_url must be a non-empty string")
    if any(character.isspace() for character in base_url):
        raise _reject_endpoint("base_url must not contain whitespace")

    try:
        parts = urlsplit(base_url)
    except ValueError as exc:
        raise _reject_endpoint("base_url is not a valid HTTP URL") from exc

    if parts.scheme.lower() != "http":
        raise _reject_endpoint("base_url must use http")
    if parts.username is not None or parts.password is not None:
        raise _reject_endpoint("base_url must not include user information")
    if parts.query or parts.fragment:
        raise _reject_endpoint("base_url must not include a query or fragment")
    if parts.path not in ("", "/"):
        raise _reject_endpoint("base_url must not include a path")

    try:
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise _reject_endpoint("base_url has an invalid host or port") from exc

    if host is None or host.casefold() not in _LOOPBACK_HOSTS:
        raise _reject_endpoint("base_url host must be 127.0.0.1, localhost, or ::1")
    if port is None:
        raise _reject_endpoint("base_url must include an explicit port")
    if not 1 <= port <= 65535:
        raise _reject_endpoint("base_url port must be between 1 and 65535")

    normalized_host = host.casefold()
    display_host = f"[{normalized_host}]" if normalized_host == "::1" else normalized_host
    return f"http://{display_host}:{port}", normalized_host, port


def _bounded_repr(value: object) -> str:
    text = value if isinstance(value, str) else "<missing>"
    if len(text) > 120:
        text = f"{text[:117]}..."
    return repr(text)


class SGLangClient:
    """A thin client for a loopback SGLang OpenAI-compatible endpoint."""

    def __init__(self, base_url: str, model_id: str, *, timeout_s: float = 120.0) -> None:
        canonical, host, port = _canonical_base_url(base_url)
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a non-empty string")
        if (
            isinstance(timeout_s, bool)
            or not isinstance(timeout_s, (int, float))
            or timeout_s <= 0
        ):
            raise ValueError("timeout_s must be a positive number")

        self.base_url = canonical
        self.model_id = model_id
        self.timeout_s = float(timeout_s)
        self._host = host
        self._port = port

    def health(self) -> HealthStatus:
        try:
            status, payload = self._send("GET", _MODELS_PATH, None)
        except InferenceError as exc:
            return HealthStatus(
                healthy=False,
                detail=f"health check failed: {exc.code.value}",
            )

        if status != 200:
            return HealthStatus(healthy=False, detail=f"models endpoint returned HTTP {status}")

        try:
            data = self._decode_json(payload)
        except InferenceError as exc:
            return HealthStatus(
                healthy=False,
                detail=f"health check failed: {exc.code.value}",
            )

        if not isinstance(data, Mapping) or not isinstance(data.get("data"), list):
            return HealthStatus(healthy=False, detail="models endpoint returned an invalid payload")

        advertised = {
            entry.get("id")
            for entry in data["data"]
            if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
        }
        if self.model_id not in advertised:
            return HealthStatus(
                healthy=False,
                model_id=self.model_id,
                detail="configured model is not advertised by the endpoint",
            )
        return HealthStatus(healthy=True, model_id=self.model_id)

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not isinstance(request, GenerationRequest):
            raise TypeError("request must be a GenerationRequest")

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "seed": request.seed,
            "max_tokens": request.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hallx_proof_envelope",
                    "strict": True,
                    "schema": request.response_schema,
                },
            },
        }
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "generation request is not JSON serializable",
            ) from exc

        started = time.perf_counter()
        status, raw_payload = self._send("POST", _CHAT_PATH, body)
        elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000.0)

        if status != 200:
            raise InferenceError(
                InferenceErrorCode.HTTP_ERROR,
                f"chat completion returned HTTP {status}",
            )

        data = self._decode_json(raw_payload)
        return self._parse_chat_completion(data, elapsed_ms)

    def _send(self, method: str, path: str, body: bytes | None) -> tuple[int, bytes]:
        connection = HTTPConnection(self._host, self._port, timeout=self.timeout_s)
        headers = {"Accept": "application/json", "Connection": "close"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
        except TimeoutError as exc:
            raise InferenceError(InferenceErrorCode.TIMEOUT, "request timed out") from exc
        except (HTTPException, OSError) as exc:
            raise InferenceError(
                InferenceErrorCode.TRANSPORT_FAILED,
                "request could not be completed",
            ) from exc
        finally:
            connection.close()

        if len(payload) > _MAX_RESPONSE_BYTES:
            raise InferenceError(
                InferenceErrorCode.MALFORMED_RESPONSE,
                "response exceeded the size limit",
            )
        return status, payload

    @staticmethod
    def _decode_json(payload: bytes) -> Any:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InferenceError(
                InferenceErrorCode.MALFORMED_RESPONSE,
                "response body was not valid UTF-8",
            ) from exc
        try:
            return json.loads(text)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise InferenceError(
                InferenceErrorCode.MALFORMED_RESPONSE,
                "response body was not valid JSON",
            ) from exc

    def _parse_chat_completion(self, data: Any, elapsed_ms: float) -> GenerationResponse:
        if not isinstance(data, Mapping):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion response must be a JSON object",
            )

        actual_model = data.get("model")
        if not isinstance(actual_model, str) or actual_model != self.model_id:
            raise InferenceError(
                InferenceErrorCode.MODEL_MISMATCH,
                f"expected model {self.model_id!r}, received {_bounded_repr(actual_model)}",
            )

        request_id = data.get("id")
        if not isinstance(request_id, str) or not request_id:
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion response is missing a request id",
            )

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion response is missing choices",
            )
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion choice must be a JSON object",
            )

        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion choice is missing a message",
            )
        raw_text = message.get("content")
        if not isinstance(raw_text, str):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion message content must be a string",
            )

        finish_reason = choice.get("finish_reason")
        if not isinstance(finish_reason, str):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion choice is missing a finish reason",
            )

        prompt_tokens, completion_tokens = self._token_usage(data.get("usage"))
        return GenerationResponse(
            raw_text=raw_text,
            model_id=actual_model,
            adapter_id=self._adapter_id(data),
            request_id=request_id,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            elapsed_ms=elapsed_ms,
        )

    @staticmethod
    def _token_usage(usage: Any) -> tuple[int | None, int | None]:
        if usage is None:
            return None, None
        if not isinstance(usage, Mapping):
            raise InferenceError(
                InferenceErrorCode.SCHEMA_INVALID,
                "chat completion usage must be a JSON object",
            )

        def token(key: str) -> int | None:
            value = usage.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InferenceError(
                    InferenceErrorCode.SCHEMA_INVALID,
                    f"chat completion usage.{key} must be a non-negative integer",
                )
            return value

        return token("prompt_tokens"), token("completion_tokens")

    @staticmethod
    def _adapter_id(data: Mapping[str, Any]) -> str | None:
        direct = data.get("adapter_id")
        if isinstance(direct, str) and direct:
            return direct
        metadata = data.get("metadata")
        if isinstance(metadata, Mapping):
            nested = metadata.get("adapter_id")
            if isinstance(nested, str) and nested:
                return nested
        return None
