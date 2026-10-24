from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import hallx.inference.sglang as sglang_module
from hallx.inference import (
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
    InferenceError,
    InferenceErrorCode,
    SGLangClient,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL = "Qwen/Qwen3-4B-Instruct-2507"
Responder = Callable[[str, str, Any], tuple[int, bytes, float]]


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads((ROOT / "configs" / "proof_envelope_schema.json").read_text(encoding="utf-8"))


def _request(schema: dict) -> GenerationRequest:
    return GenerationRequest(
        messages=(
            ChatMessage(role="system", content="Return the schema."),
            ChatMessage(role="user", content="do-not-log-this evidence"),
        ),
        response_schema=schema,
    )


def _completion(
    *,
    raw_text: str = '{"ok":true}',
    model: str = MODEL,
    request_id: str = "req-1",
) -> bytes:
    return json.dumps(
        {
            "id": request_id,
            "model": model,
            "adapter_id": "adapter-a",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": raw_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }
    ).encode("utf-8")


@contextmanager
def mock_server(responder: Responder) -> Iterator[tuple[ThreadingHTTPServer, list[dict[str, Any]]]]:
    calls: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b""
            body: Any = None
            if raw_body:
                try:
                    body = json.loads(raw_body)
                except json.JSONDecodeError:
                    body = raw_body
            calls.append({"method": method, "path": self.path, "body": body})

            status, payload, delay = responder(method, self.path, body)
            if delay:
                time.sleep(delay)
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except OSError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _base_url(server: ThreadingHTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_port}"


class _NoConnection:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("socket construction must not occur")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:30000",
        "https://127.0.0.1:30000",
        "http://127.0.0.2:30000",
        "http://10.0.0.1:30000",
        "http://localhost.evil:30000",
        "http://0.0.0.0:30000",
        "http://127.0.0.1",
        "http://127.0.0.1:0",
        "http://127.0.0.1:30000/chat",
        "http://127.0.0.1:30000?probe=1",
        "http://user@127.0.0.1:30000",
        "ftp://127.0.0.1:30000",
        " http://127.0.0.1:30000",
    ],
)
def test_inference_rejects_non_loopback(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sglang_module, "HTTPConnection", _NoConnection)
    with pytest.raises(InferenceError) as exc_info:
        SGLangClient(url, MODEL)
    assert exc_info.value.code is InferenceErrorCode.NON_LOOPBACK_ENDPOINT


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:30000", "http://127.0.0.1:30000"),
        ("http://localhost:30000", "http://localhost:30000"),
        ("http://[::1]:30000", "http://[::1]:30000"),
    ],
)
def test_inference_accepts_loopback_forms(url: str, expected: str) -> None:
    client = SGLangClient(url, MODEL)
    assert client.base_url == expected


def test_inference_success_sends_one_schema_constrained_request(
    schema: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def responder(method: str, path: str, body: Any) -> tuple[int, bytes, float]:
        if method == "POST" and path == "/v1/chat/completions":
            return 200, _completion(), 0.0
        return 404, b"{}", 0.0

    caplog.set_level(logging.INFO)
    with mock_server(responder) as (server, calls):
        client = SGLangClient(_base_url(server), MODEL, timeout_s=2)
        response = client.generate(_request(schema))

    assert len(calls) == 1
    call = calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "/v1/chat/completions"
    payload = call["body"]
    assert payload["model"] == MODEL
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 42
    assert payload["max_tokens"] == 2048
    assert payload["messages"][0] == {"role": "system", "content": "Return the schema."}
    assert payload["messages"][1] == {"role": "user", "content": "do-not-log-this evidence"}
    assert payload["response_format"]["json_schema"]["schema"] == schema
    assert "tools" not in payload
    assert "tool_choice" not in payload

    assert response.raw_text == '{"ok":true}'
    assert response.model_id == MODEL
    assert response.adapter_id == "adapter-a"
    assert response.request_id == "req-1"
    assert response.finish_reason == "stop"
    assert response.prompt_tokens == 11
    assert response.completion_tokens == 7
    assert response.elapsed_ms >= 0
    assert "do-not-log-this" not in caplog.text


def test_inference_health_is_diagnostic_and_model_aware() -> None:
    def responder(method: str, path: str, body: Any) -> tuple[int, bytes, float]:
        assert method == "GET"
        assert path == "/v1/models"
        return 200, json.dumps({"object": "list", "data": [{"id": MODEL}]}).encode(), 0.0

    with mock_server(responder) as (server, calls):
        status = SGLangClient(_base_url(server), MODEL).health()

    assert status.healthy is True
    assert status.model_id == MODEL
    assert status.detail is None
    assert len(calls) == 1


def test_inference_health_unhealthy_does_not_generate() -> None:
    def responder(method: str, path: str, body: Any) -> tuple[int, bytes, float]:
        return 200, json.dumps({"object": "list", "data": [{"id": "other"}]}).encode(), 0.0

    with mock_server(responder) as (server, calls):
        status = SGLangClient(_base_url(server), MODEL).health()

    assert status.healthy is False
    assert status.model_id == MODEL
    assert status.detail is not None
    assert len(calls) == 1


def test_inference_failures_are_typed(schema: dict) -> None:
    cases: list[tuple[int, bytes, InferenceErrorCode]] = [
        (500, b'{"error":"no"}', InferenceErrorCode.HTTP_ERROR),
        (200, b'{"truncated":', InferenceErrorCode.MALFORMED_RESPONSE),
        (
            200,
            json.dumps({"id": "r", "model": MODEL, "choices": []}).encode(),
            InferenceErrorCode.SCHEMA_INVALID,
        ),
        (200, _completion(model="another/model"), InferenceErrorCode.MODEL_MISMATCH),
    ]

    for status, payload, expected_code in cases:
        def responder(
            method: str,
            path: str,
            body: Any,
            status: int = status,
            payload: bytes = payload,
        ) -> tuple[int, bytes, float]:
            return status, payload, 0.0

        with mock_server(responder) as (server, calls):
            client = SGLangClient(_base_url(server), MODEL, timeout_s=2)
            with pytest.raises(InferenceError) as exc_info:
                client.generate(_request(schema))
        assert exc_info.value.code is expected_code
        assert len(calls) == 1


def test_inference_timeout_is_typed(schema: dict) -> None:
    def responder(method: str, path: str, body: Any) -> tuple[int, bytes, float]:
        return 200, _completion(), 0.5

    with mock_server(responder) as (server, calls):
        client = SGLangClient(_base_url(server), MODEL, timeout_s=0.05)
        with pytest.raises(InferenceError) as exc_info:
            client.generate(_request(schema))

    assert exc_info.value.code is InferenceErrorCode.TIMEOUT
    assert len(calls) == 1


def test_inference_transport_failure_is_typed(
    schema: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_request(self: object, *args: object, **kwargs: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(sglang_module.HTTPConnection, "request", fail_request)
    client = SGLangClient("http://127.0.0.1:30000", MODEL)
    with pytest.raises(InferenceError) as exc_info:
        client.generate(_request(schema))
    assert exc_info.value.code is InferenceErrorCode.TRANSPORT_FAILED


def test_inference_models_are_frozen_and_forbid_extra_fields() -> None:
    response = GenerationResponse(
        raw_text="{}",
        model_id=MODEL,
        adapter_id=None,
        request_id="r",
        finish_reason="stop",
        prompt_tokens=None,
        completion_tokens=None,
        elapsed_ms=1.0,
    )
    with pytest.raises(ValidationError):
        response.raw_text = "changed"
    with pytest.raises(ValidationError):
        GenerationResponse.model_validate({**response.model_dump(), "unexpected": True})
