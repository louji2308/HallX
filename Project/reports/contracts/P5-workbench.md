# P5 — reviewer workbench shell contract v1

OWNER: orchestrator
OBJECTIVE: Provide a local, accessible reviewer shell with the five core surfaces and DESIGN.md tokens, using clearly labeled fixtures until P3/P4 integration is available.

IN SCOPE (batch 1):
- Standard-library local HTTP shell bound to loopback, with navigation and fixture-backed pages.
- Adjudicate, Evidence Run Detail, Source Inspector, Documents/Version History, Evidence Runs, Escalations.
- Empty, loading (disabled), error, unsupported-source-map, and fixture states.
- Unit tests for rendering, tokens, no external requests, and no raw-output-as-verified.

OUT OF SCOPE:
- Real retrieval/inference calls, business logic, ACL decisions, real PDF rendering/highlighting, browser E2E proof, Gradio/PDF.js installation.
- Editing P1–P4, specs, configs, or lockfiles.
- Presenting fixtures as real evidence or a verified answer.

## FROZEN INTERFACES

Package `hallx.workbench`; standard library only. Pydantic models are frozen and `extra="forbid"`.

```text
PageResponse(status:int, content_type:str, body:str)
WorkbenchApp.page(path:str) -> PageResponse
serve(host:str="127.0.0.1", port:int=7860) -> None
build_fixture_state() -> WorkbenchState
```

Required routes:

```text
GET /                         Adjudicate
GET /runs                     Evidence Runs
GET /runs/{run_id}            Evidence Run Detail
GET /documents                Documents
GET /documents/{doc_id}/versions  Version History
GET /escalations              Escalations
GET /source/{chunk_id}        Source Inspector
GET /api/health               {"status":"ok","mode":"fixture"}
```

Rules:
- `serve` binds `127.0.0.1` by default; a non-loopback host raises `ValueError`. No outbound network, CDN, telemetry, analytics, or external font request.
- Every fixture page contains the visible text `FIXTURE DATA — NOT A VERIFIED RUN` and `data-fixture="true"`.
- Reviewer pages never render raw model output as verified. Fixture answer surfaces show only a final-state label, server-side validated fields, and an explicit `FIXTURE` badge. No unchecked candidate/JSON block.
- Source Inspector must show `SOURCE MAP UNSUPPORTED` for an unmappable fixture and must not draw a fake highlight. A mapped fixture may show offsets only if labeled `FIXTURE OFFSET — NOT A REAL HIGHLIGHT`; never claim a verified PDF highlight.
- Escalations expose audit-event metadata and reviewer/auditor separation copy; no restricted text in URLs or logs.
- Navigation uses ordinary links and visible focus styles. All pages have a `<main>`, one `<h1>`, and a skip link.
- CSS uses DESIGN.md tokens exactly: ink `#17191c`, paper `#ffffff`, mist `#f2f2f3`, peach `#fbe1d1`, sienna `#5d2a1a`; 24px card radius; pill buttons; `max-width: 1200px`. Bundled fonts absent: use `"Source Serif 4", Georgia` and `"Inter", system-ui` fallbacks; no font URL.
- Required `data-testid` hooks: `nav-adjudicate`, `nav-documents`, `nav-runs`, `nav-escalations`, `fixture-banner`, `evidence-state`, `source-unsupported`, `escalation-audit`, `empty-state`, `error-state`.

## WRITE PATHS

- `Project/src/hallx/workbench/`
- `Project/tests/unit/test_workbench*.py`
- `Project/reports/evidence/p5/` (fixture-only notes; no browser claim)
- Do not edit P1–P4, configs, specs, `pyproject.toml`, or lockfiles.

## ACCEPTANCE

```powershell
uv run pytest tests/unit -q -k "workbench"
uv run ruff check src/hallx/workbench tests/unit/test_workbench*.py
uv run python -c "from hallx.workbench.app import WorkbenchApp; a=WorkbenchApp(); r=a.page('/'); assert r.status==200; assert 'FIXTURE DATA' in r.body; print('shell ok')"
```

Pass criteria: commands exit 0; all routes render; tokens and test IDs present; fixture banner on every fixture page; no external URL/font/CDN; unsupported mapping is explicit; no raw model output rendered as verified.

## INVARIANTS / TESTS

- All routes + unknown route 404 -> `test_workbench_routes_render`.
- Fixture labeling -> `test_workbench_fixture_banner_every_page`.
- DESIGN tokens and layout -> `test_workbench_design_tokens`.
- No external requests/assets -> `test_workbench_no_external_urls`.
- Unsupported mapping not faked -> `test_workbench_source_unsupported`.
- Reviewer never sees raw output -> `test_workbench_no_raw_output_as_verified`.
- Escalation audit metadata -> `test_workbench_escalation_audit`.
- Loopback-only server -> `test_workbench_loopback_only`.

## EVIDENCE

Save unit output and a static page snapshot under `Project/reports/evidence/p5/`. Browser gate is deferred to integration after Chrome is available.

## STOP / BLOCKED

- A fixture would need real P3/P4 data to render correctly: use an explicit empty/unsupported state, do not fabricate.
- A new dependency or JS framework is required: stop and report; batch 1 is standard-library only.
- Chrome gate requested: mark blocked, not passed.

CHANGES: v1 initial (canonical 10-phase plan: P5 = reviewer workbench).
