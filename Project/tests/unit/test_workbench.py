"""Unit tests for the P5 fixture reviewer shell."""

from __future__ import annotations

import inspect
import json
import re

import pytest
from pydantic import ValidationError

from hallx.models import EvidenceState
from hallx.workbench.app import PageResponse, WorkbenchApp, _make_server, serve
from hallx.workbench.state import (
    FIXTURE_BANNER,
    OFFSET_WARNING,
    UNSUPPORTED_MAP_LABEL,
    MapStatus,
    build_fixture_state,
)

REQUIRED_TEST_IDS = (
    "nav-adjudicate",
    "nav-documents",
    "nav-runs",
    "nav-escalations",
    "fixture-banner",
    "evidence-state",
    "source-unsupported",
    "escalation-audit",
    "empty-state",
    "error-state",
)


def _app() -> WorkbenchApp:
    return WorkbenchApp()


def _html_paths() -> list[str]:
    state = build_fixture_state()
    paths = ["/", "/runs", "/documents", "/escalations"]
    paths.extend(f"/runs/{run.run_id}" for run in state.runs)
    paths.extend(f"/documents/{doc.doc_id}/versions" for doc in state.documents)
    paths.extend(f"/source/{source.chunk_id}" for source in state.sources)
    return paths


def _assert_shell(body: str) -> None:
    assert 'data-fixture="true"' in body
    assert 'data-testid="fixture-banner"' in body
    assert FIXTURE_BANNER in body
    assert '<a class="skip-link" href="#main">' in body
    assert '<main id="main"' in body
    assert body.count("<h1") == 1
    for test_id in ("nav-adjudicate", "nav-documents", "nav-runs", "nav-escalations"):
        assert f'data-testid="{test_id}"' in body


def test_workbench_routes_render() -> None:
    app = _app()

    for path in _html_paths():
        response = app.page(path)
        assert response.status == 200, path
        assert response.content_type.startswith("text/html"), path
        _assert_shell(response.body)

    for path, label in (
        ("/", "Adjudicate"),
        ("/runs", "Evidence Runs"),
        ("/documents", "Documents"),
        ("/escalations", "Escalations"),
    ):
        assert label in app.page(path).body

    assert app.page("/runs/").status == 200

    for path in (
        "/missing",
        "/runs/run-does-not-exist",
        "/documents/doc-does-not-exist/versions",
        "/source/chunk-does-not-exist",
        "/documents/doc-helios-access",
        "//example.test/path",
        "not-a-path",
        "/runs/run-fixture-supported/extra",
    ):
        response = app.page(path)
        assert response.status == 404, path
        assert 'data-testid="error-state"' in response.body
        _assert_shell(response.body)

    with pytest.raises(TypeError):
        app.page(None)  # type: ignore[arg-type]


def test_workbench_fixture_banner_every_page() -> None:
    app = _app()
    paths = _html_paths() + ["/runs/run-does-not-exist"]
    for path in paths:
        body = app.page(path).body
        assert FIXTURE_BANNER in body, path
        assert "FIXTURE DATA — NOT A VERIFIED RUN" in body, path
        assert 'data-fixture="true"' in body, path
        assert 'data-testid="fixture-banner"' in body, path


def test_workbench_design_tokens() -> None:
    body = _app().page("/").body
    for token in ("#17191c", "#ffffff", "#f2f2f3", "#fbe1d1", "#5d2a1a"):
        assert token in body
    assert "border-radius: 24px" in body
    assert "border-radius: 9999px" in body
    assert "max-width: 1200px" in body
    assert '"Source Serif 4", Georgia' in body
    assert '"Inter", system-ui' in body
    assert ":focus-visible" in body
    assert "@font-face" not in body

    required_hooks = REQUIRED_TEST_IDS
    corpus = "\n".join(
        _app().page(path).body
        for path in _html_paths() + ["/runs/run-does-not-exist"]
    )
    for test_id in required_hooks:
        assert f'data-testid="{test_id}"' in corpus, test_id


def test_workbench_no_external_urls() -> None:
    app = _app()
    paths = _html_paths() + ["/runs/run-does-not-exist", "/api/health"]
    forbidden = (
        "http://",
        "https://",
        "@import",
        "@font-face",
        "<script",
        "<link",
        "src=",
        "url(",
        "fonts.googleapis",
        "cdn.",
        ".woff",
    )
    for path in paths:
        body = app.page(path).body
        lowered = body.lower()
        for marker in forbidden:
            assert marker not in lowered, (path, marker)

    for path in _html_paths() + ["/runs/run-does-not-exist"]:
        body = app.page(path).body
        for href in re.findall(r'href="([^"]+)"', body):
            assert href.startswith(("/", "#")), (path, href)


def test_workbench_source_unsupported() -> None:
    state = build_fixture_state()
    app = _app()
    unsupported = next(
        source for source in state.sources if source.map_status is MapStatus.UNSUPPORTED
    )
    body = app.page(f"/source/{unsupported.chunk_id}").body
    assert UNSUPPORTED_MAP_LABEL in body
    assert "SOURCE MAP UNSUPPORTED" in body
    assert 'data-testid="source-unsupported"' in body
    assert 'data-testid="fixture-offset"' not in body
    assert OFFSET_WARNING not in body
    assert "Fixture character range" not in body
    assert "Fixture page label" not in body
    assert "<mark" not in body
    assert "VERIFIED HIGHLIGHT" not in body

    mapped = next(
        source for source in state.sources if source.map_status is MapStatus.MAPPED
    )
    mapped_body = app.page(f"/source/{mapped.chunk_id}").body
    assert OFFSET_WARNING in mapped_body
    assert "FIXTURE OFFSET — NOT A REAL HIGHLIGHT" in mapped_body
    assert 'data-testid="fixture-offset"' in mapped_body
    assert "Fixture page label" in mapped_body
    assert UNSUPPORTED_MAP_LABEL not in mapped_body
    assert 'data-testid="source-unsupported"' not in mapped_body
    assert "<mark" not in mapped_body
    assert "VERIFIED HIGHLIGHT" not in mapped_body


def test_workbench_no_raw_output_as_verified() -> None:
    app = _app()
    for path in _html_paths() + ["/runs/run-does-not-exist"]:
        body = app.page(path).body
        lowered = body.lower()
        assert "<pre" not in lowered, path
        assert "raw_model_output" not in lowered, path
        assert 'data-testid="raw-output"' not in lowered, path
        assert "verified answer" not in lowered, path
        assert 'data-verified="true"' not in lowered, path
        assert '"verified": true' not in lowered, path

    for path in (
        "/",
        "/runs/run-fixture-supported",
        "/runs/run-fixture-rejected",
        "/escalations",
    ):
        body = app.page(path).body
        assert "raw" in body.lower()
        assert "withheld" in body.lower() or "auditor" in body.lower()

    rejected = app.page("/runs/run-fixture-rejected").body
    assert 'data-testid="error-state"' in rejected
    assert "FAILED" in rejected
    assert "Raw candidate output is withheld" in rejected


def test_workbench_escalation_audit() -> None:
    state = build_fixture_state()
    body = _app().page("/escalations").body
    assert 'data-testid="escalation-audit"' in body
    assert "Reviewer / auditor separation" in body
    assert "A UI mode is not itself a security control." in body
    assert "Raw model output" in body

    for case in state.escalations:
        assert case.case_id in body
        assert case.run_id in body
        for event in case.audit_events:
            assert event.event_id in body
            assert event.actor_role in body
            assert event.occurred_at in body
            assert event.action in body

    for href in re.findall(r'href="([^"]+)"', body):
        assert href.startswith(("/", "#"))
        assert "?" not in href
        assert " " not in href
        assert "restricted" not in href.lower()
        assert (
            re.match(r"^/(runs|documents|source|escalations)(/[\w-]+)*$", href)
            or href == "/"
            or href.startswith("#")
        )


def test_workbench_loopback_only() -> None:
    signature = inspect.signature(serve)
    assert signature.parameters["host"].default == "127.0.0.1"

    for host in ("0.0.0.0", "192.168.1.10", "example.com", "", " "):
        with pytest.raises(ValueError):
            serve(host=host, port=0)

    server = _make_server("127.0.0.1", 0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_workbench_health() -> None:
    response = _app().page("/api/health")
    assert response.status == 200
    assert response.content_type == "application/json"
    assert json.loads(response.body) == {"status": "ok", "mode": "fixture"}


def test_workbench_empty_and_loading_states() -> None:
    body = _app().page("/").body
    assert 'data-testid="empty-state"' in body
    assert 'data-testid="loading-disabled"' in body
    assert "disabled" in body
    assert 'aria-disabled="true"' in body


def test_workbench_all_five_states_are_represented() -> None:
    state = build_fixture_state()
    observed = {run.state for run in state.runs}
    assert observed == set(EvidenceState)
    app = _app()
    for run in state.runs:
        body = app.page(f"/runs/{run.run_id}").body
        assert f'data-evidence-state="{run.state.value}"' in body
        if run.state in (EvidenceState.MISSING, EvidenceState.CONFLICTED, EvidenceState.STALE):
            assert "No validated factual claims are displayed" in body


def test_workbench_page_response_is_frozen_and_strict() -> None:
    response = PageResponse(status=200, content_type="text/html", body="ok")
    with pytest.raises(ValidationError):
        response.status = 500
    with pytest.raises(ValidationError):
        PageResponse(status=200, content_type="text/html", body="ok", extra="forbidden")
