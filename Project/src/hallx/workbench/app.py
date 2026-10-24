"""Loopback-only reviewer workbench shell for HallX-Local (P5 batch 1).

The shell is standard-library only and fixture-backed. It performs no retrieval,
generation, ACL decision, or PDF rendering; application business rules stay in
services outside this package.
"""

from __future__ import annotations

import ipaddress
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pydantic import BaseModel, ConfigDict

from hallx.workbench.render import (
    render_adjudicate,
    render_documents,
    render_escalations,
    render_not_found,
    render_run_detail,
    render_runs,
    render_source_inspector,
    render_version_history,
)
from hallx.workbench.state import WorkbenchState, build_fixture_state

_HTML = "text/html; charset=utf-8"
_JSON = "application/json"
_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
    "form-action 'none'; img-src 'none'; font-src 'none'; connect-src 'none'"
)


class PageResponse(BaseModel):
    """Frozen HTTP response returned by :meth:`WorkbenchApp.page`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: int
    content_type: str
    body: str


class WorkbenchApp:
    """Route fixture state to server-rendered reviewer pages."""

    def __init__(self, state: WorkbenchState | None = None) -> None:
        self.state = state if state is not None else build_fixture_state()
        self._runs = {run.run_id: run for run in self.state.runs}
        self._documents = {doc.doc_id: doc for doc in self.state.documents}
        self._sources = {source.chunk_id: source for source in self.state.sources}

    def page(self, path: str) -> PageResponse:
        normalized = _normalize_path(path)
        if normalized is None:
            return _not_found(self.state)
        if normalized == "/api/health":
            return PageResponse(
                status=200,
                content_type=_JSON,
                body=json.dumps({"status": "ok", "mode": "fixture"}),
            )
        if normalized == "/":
            return _html(render_adjudicate(self.state))
        if normalized == "/runs":
            return _html(render_runs(self.state))
        if normalized == "/documents":
            return _html(render_documents(self.state))
        if normalized == "/escalations":
            return _html(render_escalations(self.state))

        segments = [segment for segment in normalized.split("/") if segment]
        if len(segments) == 2 and segments[0] == "runs":
            run = self._runs.get(segments[1])
            if run is None:
                return _not_found(self.state)
            return _html(render_run_detail(self.state, run))
        if len(segments) == 3 and segments[0] == "documents" and segments[2] == "versions":
            document = self._documents.get(segments[1])
            if document is None:
                return _not_found(self.state)
            return _html(render_version_history(self.state, document))
        if len(segments) == 2 and segments[0] == "source":
            source = self._sources.get(segments[1])
            if source is None:
                return _not_found(self.state)
            return _html(render_source_inspector(self.state, source))
        return _not_found(self.state)


def _html(body: str) -> PageResponse:
    return PageResponse(status=200, content_type=_HTML, body=body)


def _not_found(state: WorkbenchState) -> PageResponse:
    return PageResponse(status=404, content_type=_HTML, body=render_not_found(state))


def _normalize_path(path: str) -> str | None:
    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if not path.startswith("/") or path.startswith("//"):
        return None
    if len(path) > 512:
        return None
    if any(character in path for character in ("\\", "\r", "\n", "\x00")):
        return None
    normalized = path.split("#", 1)[0].split("?", 1)[0]
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _validate_host(host: str) -> None:
    if not isinstance(host, str) or not host:
        raise ValueError("workbench host must be a non-empty loopback address")
    if host == "localhost":
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(
            f"workbench host must be a loopback address, got {host!r}"
        ) from exc
    if not address.is_loopback:
        raise ValueError(f"workbench host must be loopback-only, got {host!r}")


def _handler_type(app: WorkbenchApp) -> type[BaseHTTPRequestHandler]:
    class WorkbenchRequestHandler(BaseHTTPRequestHandler):
        server_version = "HallXWorkbench/0.1"
        sys_version = ""
        protocol_version = "HTTP/1.1"
        workbench_app = app

        def do_GET(self) -> None:
            self._respond(self.workbench_app.page(self.path), include_body=True)

        def do_HEAD(self) -> None:
            self._respond(self.workbench_app.page(self.path), include_body=False)

        def do_POST(self) -> None:
            response = PageResponse(
                status=405,
                content_type=_JSON,
                body=json.dumps({"error": "method_not_allowed", "mode": "fixture"}),
            )
            self._respond(response, include_body=True)

        def _respond(self, response: PageResponse, *, include_body: bool) -> None:
            payload = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            if include_body:
                self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

        log_error = log_message

    return WorkbenchRequestHandler


def _make_server(
    host: str = "127.0.0.1",
    port: int = 7860,
    *,
    app: WorkbenchApp | None = None,
) -> ThreadingHTTPServer:
    _validate_host(host)
    application = app if app is not None else WorkbenchApp()
    handler = _handler_type(application)
    server_class: type[ThreadingHTTPServer] = ThreadingHTTPServer
    if host != "localhost":
        address = ipaddress.ip_address(host)
        if address.version == 6:

            class IPv6WorkbenchServer(ThreadingHTTPServer):
                address_family = socket.AF_INET6

            server_class = IPv6WorkbenchServer
    return server_class((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 7860) -> None:
    """Serve the fixture reviewer shell on a loopback address only."""

    server = _make_server(host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


__all__ = ["PageResponse", "WorkbenchApp", "serve"]


if __name__ == "__main__":
    serve()
