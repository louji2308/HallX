"""Server-rendered HTML for the P5 reviewer workbench shell.

The renderer is deliberately dependency-free and read-only. It presents only
fixture records from :mod:`hallx.workbench.state`; it never executes business
rules, calls a model, or claims a verified run or PDF highlight.
"""

from __future__ import annotations

from html import escape

from hallx.models import EvidenceState
from hallx.workbench.state import (
    DocumentFixture,
    EscalationFixture,
    RunFixture,
    SourceFixture,
    VersionStatus,
    WorkbenchState,
)

_CSS = """
:root {
  --color-ink-black: #17191c;
  --color-paper-white: #ffffff;
  --color-mist-gray: #f2f2f3;
  --color-fog-white: #fafafb;
  --color-slate-gray: #777b86;
  --color-ash-gray: #979799;
  --color-blush-peach: #fbe1d1;
  --color-sienna-brown: #5d2a1a;
  --page-max-width: 1200px;
  --font-signifier: "Source Serif 4", Georgia, ui-serif, serif;
  --font-sohne: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--color-paper-white);
  color: var(--color-ink-black);
  font-family: var(--font-sohne);
  font-size: 17px;
  line-height: 1.35;
}
a { color: var(--color-ink-black); text-underline-offset: 0.2em; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible {
  outline: 3px solid var(--color-ink-black);
  outline-offset: 3px;
  box-shadow: 0 0 0 6px var(--color-blush-peach);
}
h1, h2, h3 {
  font-family: var(--font-signifier);
  font-weight: 400;
  margin: 0;
}
h1 { font-size: 44px; line-height: 1.3; letter-spacing: -0.66px; }
h2 { font-size: 26px; line-height: 1.18; letter-spacing: -0.23px; }
h3 { font-size: 22px; line-height: 1.5; }
p { margin: 0 0 12px; }
.shell { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.skip-link {
  position: absolute;
  left: 16px;
  top: -80px;
  z-index: 20;
  padding: 12px 20px;
  border-radius: 9999px;
  background: var(--color-ink-black);
  color: var(--color-paper-white);
}
.skip-link:focus { top: 16px; }
.topbar { padding: 20px 0 12px; }
.topbar-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}
.brand { font-family: var(--font-signifier); font-size: 22px; }
.role-chip {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 10px;
  border: 1px solid var(--color-ink-black);
  border-radius: 9999px;
  font-family: var(--font-sohne);
  font-size: 12px;
  letter-spacing: 0.08em;
  vertical-align: middle;
}
nav ul {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
nav a {
  display: inline-block;
  padding: 8px 14px;
  border-radius: 9999px;
  text-decoration: none;
}
nav a:hover { background: var(--color-mist-gray); }
nav a[aria-current="page"] {
  border: 1px solid var(--color-ink-black);
  background: var(--color-mist-gray);
}
.fixture-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: baseline;
  margin: 8px 0 24px;
  padding: 16px 20px;
  border-radius: 24px;
  background: var(--color-blush-peach);
  color: var(--color-sienna-brown);
}
.fixture-banner strong { letter-spacing: 0.04em; }
.fixture-banner span { font-size: 15px; }
main { display: block; padding-bottom: 64px; }
.page-head { margin: 8px 0 24px; }
.lede { max-width: 72ch; color: var(--color-slate-gray); font-size: 18px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
}
.card {
  padding: 24px;
  border-radius: 24px;
  background: var(--color-mist-gray);
}
.card-white {
  padding: 24px;
  border: 1px solid var(--color-mist-gray);
  border-radius: 24px;
  background: var(--color-paper-white);
}
.card h2 { margin-bottom: 12px; }
.card h3 { margin-bottom: 8px; }
.stack > * + * { margin-top: 24px; }
.muted { color: var(--color-slate-gray); }
.meta { color: var(--color-slate-gray); font-size: 15px; }
.state-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.state-badge {
  display: inline-block;
  padding: 6px 12px;
  border: 1px solid var(--color-ink-black);
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.06em;
}
.fixture-badge {
  display: inline-block;
  padding: 6px 12px;
  border: 1px dashed var(--color-ink-black);
  border-radius: 9999px;
  font-size: 12px;
  letter-spacing: 0.1em;
}
.button {
  display: inline-block;
  min-height: 44px;
  padding: 10px 20px;
  border: 1px solid var(--color-ink-black);
  border-radius: 9999px;
  background: var(--color-ink-black);
  color: var(--color-paper-white);
  font: inherit;
}
.button[disabled] {
  opacity: 0.55;
  cursor: not-allowed;
}
.button-ghost {
  display: inline-block;
  min-height: 44px;
  padding: 10px 20px;
  border: 1px solid var(--color-ink-black);
  border-radius: 9999px;
  background: transparent;
  color: var(--color-ink-black);
  font: inherit;
  text-decoration: none;
}
label { display: block; margin: 16px 0 6px; font-weight: 500; }
input, textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--color-ash-gray);
  border-radius: 16px;
  background: var(--color-paper-white);
  color: var(--color-ink-black);
  font: inherit;
}
input[disabled], textarea[disabled] { color: var(--color-slate-gray); }
.loading-preview {
  margin-top: 16px;
  padding: 12px 16px;
  border: 1px dashed var(--color-ash-gray);
  border-radius: 16px;
  color: var(--color-slate-gray);
  font-size: 15px;
}
.banner-note { margin-top: 12px; font-size: 15px; }
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-paper-white);
  border-radius: 16px;
}
caption {
  padding: 8px 0;
  color: var(--color-slate-gray);
  font-size: 15px;
  text-align: left;
}
th, td {
  padding: 12px;
  border-bottom: 1px solid var(--color-mist-gray);
  text-align: left;
  vertical-align: top;
}
th { font-size: 14px; letter-spacing: 0.04em; }
blockquote {
  margin: 0;
  padding-left: 12px;
  border-left: 3px solid var(--color-ink-black);
}
.list { margin: 0; padding-left: 20px; }
.list li + li { margin-top: 8px; }
.state-legend {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.state-legend li {
  padding: 12px;
  border: 1px solid var(--color-mist-gray);
  border-radius: 16px;
  background: var(--color-paper-white);
}
.state-legend strong { display: block; font-size: 14px; letter-spacing: 0.05em; }
.state-legend span { color: var(--color-slate-gray); font-size: 14px; }
.offset-note {
  margin-top: 16px;
  padding: 16px;
  border: 2px dashed var(--color-ink-black);
  border-radius: 16px;
}
.unsupported {
  border: 2px solid var(--color-ink-black);
  background: var(--color-fog-white);
}
.error-card {
  border: 2px solid var(--color-ink-black);
  background: var(--color-fog-white);
}
.error-label {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.08em;
}
.chunk-text {
  padding: 20px;
  border-radius: 16px;
  background: var(--color-paper-white);
  font-family: var(--font-signifier);
  font-size: 20px;
  line-height: 1.5;
}
.footer {
  padding: 24px 0 40px;
  border-top: 1px solid var(--color-mist-gray);
  color: var(--color-slate-gray);
  font-size: 14px;
}
.breadcrumb { margin-bottom: 12px; font-size: 15px; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
"""

_STATE_LEGEND = (
    (
        EvidenceState.SUPPORTED,
        "All required premises are established by active, authorized sources.",
    ),
    (
        EvidenceState.PARTIAL,
        "Some premises are supported; at least one explicit premise is missing.",
    ),
    (
        EvidenceState.MISSING,
        "No sufficient source-backed answer is available; no factual claims.",
    ),
    (
        EvidenceState.CONFLICTED,
        "Two active sources disagree; both spans require human review.",
    ),
    (
        EvidenceState.STALE,
        "Only an expired or superseded source matches; stale text is not current support.",
    ),
)


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _nav(active: str) -> str:
    items = (
        ("adjudicate", "/", "Adjudicate"),
        ("documents", "/documents", "Documents"),
        ("runs", "/runs", "Evidence Runs"),
        ("escalations", "/escalations", "Escalations"),
    )
    links = []
    for key, href, label in items:
        current = ' aria-current="page"' if key == active else ""
        links.append(
            f'<li><a data-testid="nav-{key}" href="{href}"{current}>{_e(label)}</a></li>'
        )
    return (
        '<nav aria-label="Reviewer sections"><ul>'
        + "".join(links)
        + "</ul></nav>"
    )


def _layout(state: WorkbenchState, *, title: str, active: str, content: str) -> str:
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'; '
        'base-uri \'none\'; form-action \'none\'; img-src \'none\'; '
        'font-src \'none\'; connect-src \'none\';">'
        f"<title>{_e(title)} — HallX-Local Reviewer (fixture)</title>"
        f"<style>{_CSS}</style>"
        "</head>"
        '<body data-fixture="true">'
        '<a class="skip-link" href="#main">Skip to main content</a>'
        '<header class="topbar"><div class="shell topbar-inner">'
        '<div class="brand">HallX-Local'
        '<span class="role-chip">REVIEWER MODE · FIXTURE</span></div>'
        f"{_nav(active)}"
        "</div></header>"
        '<div class="shell"><div class="fixture-banner" data-testid="fixture-banner" '
        'role="status">'
        f"<strong>{_e(state.fixture_banner)}</strong>"
        "<span>No live model, retrieval, ACL check, or PDF highlight was executed "
        "for these pages.</span>"
        "</div></div>"
        '<main id="main" class="shell" tabindex="-1">'
        f"{content}"
        "</main>"
        '<footer class="footer"><div class="shell">'
        "Local-only fixture shell. No network requests, telemetry, external fonts, "
        "or CDN assets. Business rules stay in application services, not in this UI."
        "</div></footer>"
        "</body></html>"
    )


def _state_badge(state: WorkbenchState, value: EvidenceState) -> str:
    return (
        '<div class="state-line">'
        f'<span class="state-badge" data-testid="evidence-state" '
        f'data-evidence-state="{_e(value.value)}">{_e(value.value)}</span>'
        f'<span class="fixture-badge">{_e(state.fixture_badge)}</span>'
        "</div>"
    )


def _source_link(chunk_id: str, label: str = "Open Source Inspector") -> str:
    return f'<a href="/source/{_e(chunk_id)}">{_e(label)}</a>'


def _claim_table(state: WorkbenchState, run: RunFixture) -> str:
    if not run.claims:
        return (
            '<p class="muted">No validated factual claims are displayed for this state. '
            "Reviewer mode never substitutes raw model prose for a verified claim.</p>"
        )
    rows = []
    for claim in run.claims:
        rows.append(
            "<tr>"
            f"<td>{_e(claim.claim_id)}</td>"
            f"<td>{_e(claim.text)}<br><span class=\"meta\">"
            f"{_e(claim.support_status.value)}</span></td>"
            f"<td><blockquote>{_e(claim.quote)}</blockquote></td>"
            f"<td>{_e(claim.numeric_check)}</td>"
            f"<td>{_source_link(claim.chunk_id, 'Inspect cited chunk')}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<caption>Validated fixture claim records only. No unchecked candidate output "
        "is rendered here.</caption>"
        "<thead><tr><th scope=\"col\">Claim</th><th scope=\"col\">Displayed claim</th>"
        "<th scope=\"col\">Exact fixture quote</th><th scope=\"col\">Numeric check</th>"
        "<th scope=\"col\">Source</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        '<p class="banner-note muted">Entailment and numeric results are fixture '
        "labels, not executed checks. No raw candidate output is exposed in reviewer "
        "mode.</p>"
    )


def _state_legend() -> str:
    items = []
    for state, description in _STATE_LEGEND:
        items.append(
            f"<li><strong>{_e(state.value)}</strong><span>{_e(description)}</span></li>"
        )
    return (
        '<section class="card" aria-labelledby="state-legend-title">'
        '<h2 id="state-legend-title">Five-state reference (fixture legend)</h2>'
        f'<ul class="state-legend">{"".join(items)}</ul>'
        "</section>"
    )


def render_adjudicate(state: WorkbenchState) -> str:
    runs = {run.run_id: run for run in state.runs}
    run = runs[state.adjudicate.run_id]
    content = (
        '<section class="page-head">'
        "<h1>Adjudicate</h1>"
        '<p class="lede">Ask a question over an authorized scope and inspect the '
        "server-owned final state. Submission is disabled in this fixture shell; the "
        "result below is a labeled fixture record, not a run you started.</p>"
        "</section>"
        '<div class="grid">'
        '<section class="card" aria-labelledby="question-title">'
        '<h2 id="question-title">Question form</h2>'
        '<label for="scope">Document scope</label>'
        f'<input id="scope" name="scope" value="{_e(state.adjudicate.scope)}" disabled>'
        '<label for="question">Question</label>'
        f'<textarea id="question" name="question" rows="4" disabled>{_e(run.question)}'
        "</textarea>"
        '<p class="banner-note"><button class="button" type="button" disabled>'
        "Run adjudication — disabled in fixture</button></p>"
        '<div class="loading-preview" data-testid="loading-disabled" role="status" '
        'aria-disabled="true">Loading state preview — generation is disabled and no '
        "request will be sent.</div>"
        "</section>"
        '<section class="card" data-testid="empty-state" aria-labelledby="empty-title">'
        '<h2 id="empty-title">Empty state</h2>'
        "<p>No submission is attached to this form. Nothing is queued, loading, or "
        "running.</p>"
        '<p class="muted">Use the fixture result below to review the final-state '
        "surface, or open Evidence Runs for the labeled fixture set.</p>"
        "</section>"
        "</div>"
        '<div class="stack">'
        '<section class="card-white" aria-labelledby="result-title">'
        '<h2 id="result-title">Fixture result — latest seeded run</h2>'
        f"{_state_badge(state, run.state)}"
        f'<p class="meta">Run {_e(run.run_id)} · {_e(run.created_at)} · '
        f"{_e(run.status.value)}</p>"
        f"<p><strong>Question:</strong> {_e(run.question)}</p>"
        f"<p><strong>Scope:</strong> {_e(run.scope)}</p>"
        f"<p>{_e(run.summary)}</p>"
        f"{_claim_table(state, run)}"
        '<div class="grid">'
        '<div class="card"><h3>Diagnostic</h3>'
        f"<p>{_e(run.diagnostic)}</p></div>"
        '<div class="card"><h3>Recommended action</h3>'
        f"<p>{_e(run.recommended_action)}</p></div>"
        "</div>"
        '<p class="muted">Raw model output, debug traces, and training internals are '
        "auditor-only and withheld from reviewer mode.</p>"
        '<p class="banner-note">'
        f'<a class="button-ghost" href="/runs/{_e(run.run_id)}">Open Evidence Run Detail'
        "</a> "
        f'<a class="button-ghost" href="/source/chunk-access-v2-mfa">'
        "Open Source Inspector</a></p>"
        "</section>"
        f"{_state_legend()}"
        "</div>"
    )
    return _layout(state, title="Adjudicate", active="adjudicate", content=content)


def render_runs(state: WorkbenchState) -> str:
    rows = []
    for run in state.runs:
        rows.append(
            "<tr>"
            f'<td><a href="/runs/{_e(run.run_id)}">{_e(run.run_id)}</a></td>'
            f"<td>{_e(run.question)}</td>"
            f'<td><span class="state-badge">{_e(run.state.value)}</span></td>'
            f"<td>{_e(run.status.value)}</td>"
            f"<td>{_e(run.created_at)}</td>"
            "</tr>"
        )
    content = (
        '<section class="page-head">'
        "<h1>Evidence Runs</h1>"
        '<p class="lede">Reopen frozen fixture runs with their final state, evidence '
        "bundle, and audit metadata. Every row is synthetic and unverified.</p>"
        "</section>"
        '<section class="card-white">'
        '<div class="table-wrap"><table>'
        "<caption>Fixture run index — no retrieval or generation was executed.</caption>"
        '<thead><tr><th scope="col">Run</th><th scope="col">Question</th>'
        '<th scope="col">Final state</th><th scope="col">Status</th>'
        '<th scope="col">Recorded</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "</section>"
        '<p class="banner-note"><a class="button-ghost" href="/">Back to Adjudicate</a></p>'
    )
    return _layout(state, title="Evidence Runs", active="runs", content=content)


def _chunk_table(state: WorkbenchState, run: RunFixture) -> str:
    if not run.chunks:
        return (
            '<p class="muted" data-testid="empty-bundle">The fixture evidence bundle is '
            "empty. No chunks are shown.</p>"
        )
    rows = []
    for chunk in run.chunks:
        rows.append(
            "<tr>"
            f"<td>{_e(chunk.chunk_id)}</td>"
            f"<td>{_e(chunk.triage.value)}</td>"
            f"<td>{_e(chunk.reason)}</td>"
            f"<td>{_source_link(chunk.chunk_id)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<caption>Fixture evidence bundle. ACL scope is synthetic; no permission "
        "decision was executed.</caption>"
        '<thead><tr><th scope="col">Chunk</th><th scope="col">Triage</th>'
        '<th scope="col">Reason</th><th scope="col">Source</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _trace_table(run: RunFixture) -> str:
    rows = []
    for event in run.trace:
        rows.append(
            "<tr>"
            f"<td>{_e(event.event_id)}</td>"
            f"<td>{_e(event.stage)}</td>"
            f"<td>{_e(event.outcome)}</td>"
            f"<td>{_e(event.recorded_at)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<caption>Fixture trace. Timings and live pipeline stages are deliberately "
        "absent.</caption>"
        '<thead><tr><th scope="col">Event</th><th scope="col">Stage</th>'
        '<th scope="col">Outcome</th><th scope="col">Recorded</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_run_detail(state: WorkbenchState, run: RunFixture) -> str:
    parts = [
        '<section class="page-head">',
        '<p class="breadcrumb"><a href="/runs">Evidence Runs</a> / Detail</p>',
        "<h1>Evidence Run Detail</h1>",
        (
            f'<p class="lede">Run {_e(run.run_id)} · recorded {_e(run.created_at)} · '
            f"fixture status {_e(run.status.value)}.</p>"
        ),
        "</section>",
    ]
    if run.status.value == "FAILED":
        parts.append(
            '<section class="card error-card" data-testid="error-state" role="alert">'
            '<span class="error-label">ERROR — SAFE ABSTENTION</span>'
            "<h2>Validation failed</h2>"
            f"<p>{_e(run.error or '')}</p>"
            "<p>At most one bounded repair is allowed. Authorization, ACL, integrity, "
            "identity, freshness, and stale-source failures are never repaired.</p>"
            "</section>"
        )
    parts.extend(
        [
            '<div class="stack">',
            '<section class="card-white">',
            f"{_state_badge(state, run.state)}",
            "<h2>Fixture summary — validated fields only</h2>",
            f"<p>{_e(run.summary)}</p>",
            f"<p><strong>Question:</strong> {_e(run.question)}</p>",
            f"<p><strong>Scope:</strong> {_e(run.scope)}</p>",
            (
                '<p class="muted">This summary is a fixture record. Reviewer mode '
                "displays validated fields only and withholds raw model output.</p>"
            ),
            "</section>",
            '<section class="card-white">',
            "<h2>Validated claims</h2>",
            f"{_claim_table(state, run)}",
            "</section>",
            '<div class="grid">',
            '<section class="card"><h3>Diagnostic</h3>',
            f"<p>{_e(run.diagnostic)}</p></section>",
            '<section class="card"><h3>Recommended action</h3>',
            f"<p>{_e(run.recommended_action)}</p>",
            (
                f'<p class="meta">Repair attempts recorded: {run.repair_attempts} '
                "(fixture maximum: 1).</p>"
            ),
            "</section>",
            "</div>",
            '<section class="card-white"><h2>Evidence bundle</h2>',
            f"{_chunk_table(state, run)}</section>",
            '<section class="card-white"><h2>Run trace</h2>',
            f"{_trace_table(run)}</section>",
        ]
    )
    if run.escalation_id:
        parts.append(
            '<section class="card"><h3>Escalation</h3>'
            f'<p><a href="/escalations">Open escalation case '
            f"{_e(run.escalation_id)}</a></p></section>"
        )
    parts.append(
        '<section class="card"><h3>Reviewer / auditor separation</h3>'
        "<p>Reviewer mode displays adjudication and escalation records only. Raw model "
        "output, debug traces, and training internals belong to ML Auditor mode and "
        "remain access-controlled. A UI mode is not itself a security control.</p>"
        "</section>"
        "</div>"
        '<p class="banner-note"><a class="button-ghost" href="/runs">Back to Evidence '
        "Runs</a></p>"
    )
    return _layout(state, title="Evidence Run Detail", active="runs", content="".join(parts))


def render_documents(state: WorkbenchState) -> str:
    cards = []
    for doc in state.documents:
        active = next(
            version for version in doc.versions if version.status is VersionStatus.ACTIVE
        )
        roles = ", ".join(active.acl_roles)
        cards.append(
            '<section class="card-white">'
            f"<h2>{_e(doc.title)}</h2>"
            f'<p class="meta">Document {_e(doc.doc_id)} · {_e(doc.authority)}</p>'
            f"<p><strong>Owner:</strong> {_e(doc.owner)}</p>"
            f"<p><strong>Active version:</strong> {_e(active.label)} · effective "
            f"from {_e(active.effective_from)}</p>"
            f"<p><strong>ACL roles (fixture):</strong> {_e(roles)}</p>"
            f"<p><strong>Source digest:</strong> {_e(active.digest_label)}</p>"
            f'<p><a class="button-ghost" href="/documents/{_e(doc.doc_id)}/versions">'
            "Open Version History</a></p>"
            "</section>"
        )
    content = (
        '<section class="page-head">'
        "<h1>Documents</h1>"
        '<p class="lede">Browse synthetic fixture documents and their version '
        "metadata. No file was imported, extracted, or indexed for these records.</p>"
        "</section>"
        f'<div class="stack">{"".join(cards)}</div>'
    )
    return _layout(state, title="Documents", active="documents", content=content)


def render_version_history(state: WorkbenchState, doc: DocumentFixture) -> str:
    rows = []
    for version in doc.versions:
        effective_to = version.effective_to or "open"
        supersedes = version.supersedes or "—"
        chunk_links = ", ".join(
            f'<a href="/source/{_e(chunk_id)}">{_e(chunk_id)}</a>'
            for chunk_id in version.chunk_ids
        )
        rows.append(
            "<tr>"
            f"<td>{_e(version.label)}</td>"
            f"<td>{_e(version.status.value)}</td>"
            f"<td>{_e(version.effective_from)} to {_e(effective_to)}</td>"
            f"<td>{_e(supersedes)}</td>"
            f"<td>{_e(', '.join(version.acl_roles))}</td>"
            f"<td>{_e(version.digest_label)}</td>"
            f"<td>{chunk_links}</td>"
            "</tr>"
        )
    content = (
        '<section class="page-head">'
        '<p class="breadcrumb"><a href="/documents">Documents</a> / Version History</p>'
        f"<h1>Version History — {_e(doc.title)}</h1>"
        f'<p class="lede">{_e(doc.authority)} · owner {_e(doc.owner)}. Effective '
        "windows and supersession links are synthetic fixture values.</p>"
        "</section>"
        '<section class="card-white">'
        '<div class="table-wrap"><table>'
        "<caption>Fixture version timeline. Digests are not computed.</caption>"
        '<thead><tr><th scope="col">Version</th><th scope="col">Status</th>'
        '<th scope="col">Effective window</th><th scope="col">Supersedes</th>'
        '<th scope="col">ACL roles</th><th scope="col">Source digest</th>'
        '<th scope="col">Chunks</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "</section>"
        '<section class="card"><h2>Precedence rule</h2>'
        "<p>Only an active version inside its effective window may support a current "
        "answer. Superseded versions remain visible for diagnostics but never become "
        "current support. An unresolved metadata conflict requires an authorized owner "
        "decision.</p>"
        '<p class="muted">This is descriptive fixture copy, not an executable business '
        "rule in the UI.</p></section>"
        '<p class="banner-note"><a class="button-ghost" href="/documents">Back to '
        "Documents</a></p>"
    )
    return _layout(
        state,
        title="Version History",
        active="documents",
        content=content,
    )


def _audit_table(case: EscalationFixture) -> str:
    rows = []
    for event in case.audit_events:
        rows.append(
            "<tr>"
            f"<td>{_e(event.event_id)}</td>"
            f"<td>{_e(event.occurred_at)}</td>"
            f"<td>{_e(event.actor)} ({_e(event.actor_role)})</td>"
            f"<td>{_e(event.action)}</td>"
            f"<td>{_e(event.from_status)} → {_e(event.to_status)}</td>"
            f"<td>{_e(event.detail)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap" data-testid="escalation-audit"><table>'
        "<caption>Fixture audit events with actor role, timestamp, action, and state "
        "transition.</caption>"
        '<thead><tr><th scope="col">Event</th><th scope="col">Occurred</th>'
        '<th scope="col">Actor</th><th scope="col">Action</th>'
        '<th scope="col">Transition</th><th scope="col">Detail</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_escalations(state: WorkbenchState) -> str:
    cards = []
    for case in state.escalations:
        cards.append(
            '<section class="card-white">'
            f"<h2>Case {_e(case.case_id)}</h2>"
            f'<p class="meta">Reason {_e(case.reason)} · status {_e(case.status)} · '
            f"opened {_e(case.opened_at)}</p>"
            f'<p><strong>Linked run:</strong> <a href="/runs/{_e(case.run_id)}">'
            f"{_e(case.run_id)}</a></p>"
            f"<p><strong>Reviewer:</strong> {_e(case.reviewer)} · "
            f"<strong>Owner:</strong> {_e(case.owner)}</p>"
            f"<p><strong>Decision:</strong> {_e(case.decision)}</p>"
            f"<p><strong>Rationale:</strong> {_e(case.rationale)}</p>"
            "<h3>Audit events</h3>"
            f"{_audit_table(case)}"
            "</section>"
        )
    content = (
        '<section class="page-head">'
        "<h1>Escalations</h1>"
        '<p class="lede">Missing, partial, conflicted, stale, or rejected fixture cases '
        "with human decisions and audit metadata.</p>"
        "</section>"
        '<section class="card" data-testid="access-separation">'
        "<h2>Reviewer / auditor separation</h2>"
        "<p>Reviewer mode displays adjudication and escalation records only. Raw model "
        "output, debug traces, and training internals are available only in ML Auditor "
        "mode and remain filtered by role and document ACL.</p>"
        '<p class="muted">A UI mode is not itself a security control. No restricted '
        "document text is placed in URLs or logs by this shell.</p>"
        "</section>"
        f'<div class="stack">{"".join(cards)}</div>'
    )
    return _layout(state, title="Escalations", active="escalations", content=content)


def render_source_inspector(state: WorkbenchState, source: SourceFixture) -> str:
    linked_run = next(
        (
            run.run_id
            for run in state.runs
            if any(chunk.chunk_id == source.chunk_id for chunk in run.chunks)
        ),
        None,
    )
    parts = [
        '<section class="page-head">',
        '<p class="breadcrumb"><a href="/runs">Evidence Runs</a> / Source Inspector</p>',
        "<h1>Source Inspector</h1>",
        (
            f'<p class="lede">{_e(source.doc_title)} · version '
            f"{_e(source.version_label)} · chunk {_e(source.chunk_id)}.</p>"
        ),
        "</section>",
        '<section class="card">',
        "<h2>Source metadata</h2>",
        (
            f"<p><strong>Document:</strong> {_e(source.doc_id)} · "
            f"<strong>Version:</strong> {_e(source.version_label)}</p>"
        ),
        (
            f"<p><strong>ACL scope (fixture):</strong> reviewer, auditor · "
            f"<strong>Mapping:</strong> {_e(source.map_status.value)}</p>"
        ),
        (
            f"<p><strong>Fixture page label:</strong> {_e(source.page_label)}</p>"
            if source.map_status.value == "MAPPED"
            else "<p><strong>Location:</strong> unavailable — no provable page "
            "mapping.</p>"
        ),
        "</section>",
        '<section class="card-white">',
        "<h2>Chunk text</h2>",
        f'<p class="chunk-text">{_e(source.chunk_text)}</p>',
    ]
    if source.map_status.value == "UNSUPPORTED":
        parts.append(
            '<section class="unsupported" data-testid="source-unsupported" role="status">'
            f'<span class="error-label">{_e(state.unsupported_label)}</span>'
            "<h2>No provable source mapping</h2>"
            f"<p>{_e(source.map_reason)}</p>"
            "<p>No character offsets, page region, or highlight are rendered because the "
            "server cannot prove a character-to-page mapping for this chunk.</p>"
            "</section>"
        )
    else:
        parts.append(
            '<div class="offset-note" data-testid="fixture-offset" role="note">'
            f"<strong>{_e(state.offset_warning)}</strong>"
            f"<p>Fixture character range: {_e(source.char_start)}–"
            f"{_e(source.char_end)} (canonical fixture text). This is not a "
            "server-verified span and no PDF highlight is drawn.</p>"
            "</div>"
        )
    parts.append(
        '<p class="banner-note">This shell is not a PDF viewer. PDF.js integration and '
        "verified highlighting are out of scope for this batch.</p>"
        "</section>"
    )
    if linked_run:
        parts.append(
            f'<p class="banner-note"><a class="button-ghost" href="/runs/'
            f'{_e(linked_run)}">Back to linked Evidence Run</a></p>'
        )
    else:
        parts.append(
            '<p class="banner-note"><a class="button-ghost" href="/runs">Back to '
            "Evidence Runs</a></p>"
        )
    return _layout(state, title="Source Inspector", active="runs", content="".join(parts))


def render_not_found(state: WorkbenchState) -> str:
    content = (
        '<section class="page-head"><h1>Page not found</h1>'
        '<p class="lede">The requested fixture route does not exist.</p></section>'
        '<section class="card error-card" data-testid="error-state" role="alert">'
        '<span class="error-label">ERROR — 404</span>'
        "<h2>Unknown route</h2>"
        "<p>No page is rendered for this address. Choose a reviewer section from the "
        "navigation.</p>"
        "</section>"
        '<p class="banner-note"><a class="button-ghost" href="/">Back to Adjudicate</a>'
        "</p>"
    )
    return _layout(state, title="Not found", active="", content=content)


__all__ = [
    "render_adjudicate",
    "render_documents",
    "render_escalations",
    "render_not_found",
    "render_run_detail",
    "render_runs",
    "render_source_inspector",
    "render_version_history",
]
