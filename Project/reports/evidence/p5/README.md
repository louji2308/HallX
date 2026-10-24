# P5 workbench — batch 1 evidence

**Status:** fixture shell implemented and tested; browser gate **not run** (deferred).
**Scope:** `src/hallx/workbench/` + `tests/unit/test_workbench.py` only. No P1–P4,
config, spec, dependency, or lockfile edits. Nothing here is a real adjudication run.

## What exists

- Standard-library loopback HTTP shell (`ThreadingHTTPServer`) with routes:
  `/`, `/runs`, `/runs/{id}`, `/documents`, `/documents/{id}/versions`,
  `/escalations`, `/source/{chunk_id}`, `/api/health`.
- `WorkbenchApp.page()` is directly testable and returns a frozen `PageResponse`.
- `serve()` defaults to `127.0.0.1` and raises `ValueError` for non-loopback hosts.
- Fixture state covers all five evidence states plus a failed/rejected run, mapped and
  unsupported source mappings, documents/version history, and an escalation with audit
  events.
- Every HTML page carries `FIXTURE DATA — NOT A VERIFIED RUN`, `data-fixture="true"`,
  a skip link, one `<h1>`, a `<main>`, visible focus, and the required test IDs.
- Unsupported mapping shows `SOURCE MAP UNSUPPORTED` with no offsets or `<mark>`.
  Mapped fixture offsets are labeled `FIXTURE OFFSET — NOT A REAL HIGHLIGHT`.
- No raw model output, candidate JSON, scripts, external fonts, CDNs, images, or
  outbound URLs are rendered.

## Commands and results

| Command | Exit | Key output |
|---|---|---|
| `uv run pytest tests/unit -q -k "workbench"` | 0 | `12 passed, 156 deselected` |
| `uv run ruff check src/hallx/workbench tests/unit/test_workbench.py` | 0 | `All checks passed!` |
| `uv run python -c "from hallx.workbench.app import WorkbenchApp; ... print('shell ok')"` | 0 | `shell ok` |
| `uv run pytest -q` | 0 | `190 passed in 33.15s` |
| Loopback HTTP smoke (manual, `_make_server` + `http.client`) | 0 | `/ =200, health=200, missing=404; external=0` |

Logs: `logs/pytest-workbench.txt`, `logs/ruff-workbench.txt`,
`logs/smoke-workbench.txt`, `logs/pytest-full.txt`,
`logs/http-loopback-smoke.txt`.

## Static snapshots (not browser screenshots)

`snapshots/` contains server-rendered HTML captured from `WorkbenchApp.page()`:
`adjudicate.html`, `runs.html`, `run-supported.html`, `run-rejected.html`,
`documents.html`, `version-history.html`, `escalations.html`,
`source-mapped.html`, `source-unsupported.html`, `not-found.html`,
`health.json`.

No Chrome DevTools run, screenshot, console check, or network-panel check was
performed. The P5 browser gate remains deferred until integration.

## Contract notes / flags for the orchestrator

1. Placement of the empty state is unspecified by the contract. It is rendered on
   Adjudicate as the pre-submission state; all list surfaces intentionally carry
   fixture records so the five-state and error paths can be reviewed.
2. `/api/health` is JSON and is not treated as a fixture page; it has no banner.
   Unknown HTML routes and unknown fixture IDs return a 404 that does include the
   fixture banner and `error-state` hook.
3. A loopback literal (including `::1`) or `localhost` is accepted; `0.0.0.0`,
   LAN addresses, and DNS names raise `ValueError`. The default remains
   `127.0.0.1`.
4. The rejected run keeps the frozen five-state set: status `FAILED` plus final
   state `MISSING` for safe abstention. No sixth `ERROR` evidence state was added.
5. No P3/P4 service wiring was attempted. Live retrieval/inference, ACL decisions,
   and PDF highlighting remain out of scope for this batch.
