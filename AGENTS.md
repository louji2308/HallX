# AGENTS.md — HallX-Local

Read this before editing. It is the operating contract for this repo, not a status report.

## 0. Current state (re-verify before relying)

- `Project/` is docs-only: `IDEA.md`, `ARCHITECTURE.md`, `WORKFLOWS.md`, `IMPLEMENTATION_PLAN.md`, `Tools And product Requirements.md`, `DESIGN.md`. There is no `pyproject.toml`, `uv.lock`, `src/`, `tests/`, or git-tracked code.
- Project root is `Project/`. Create code, configs, tests, and reports there — not in the `HallX/` wrapper.
- Host at authoring time: Windows + PowerShell 5.1, Python 3.11, `uv`, Node 24, ~15 GB RAM. `python3` is absent; `nvidia-smi` is absent, so assume no local GPU until proven.
- `HallX/` is untracked inside the enclosing `C:\Users\LOUJAN B` git repo (remote is `HireX-Bot`). Treat `HallX/` as the project, never stage the home directory or unrelated projects, and never `git add -A`, `git add .`, push, force-push, or change remotes. Phase commits are required — see §5.6 — but there is no dedicated HallX repo yet; establish or confirm one in Phase 0 before committing.
- Naming drift: `IDEA.md` says **HallX-Local** / `src/HallX/`; `ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md` say **ProofCite-Local** / `src/proofcite/`. Canonical for this repo: product **HallX-Local**, Python package **`hallx`**, code root **`Project/`**. Do not create `src/proofcite/`, `src/HallX/`, or a second package. Update stale doc references only when touching them; never rename mid-phase.

## 1. Source of truth (read in this order)

1. `Project/IDEA.md` — product thesis, scope, pins, evaluation protocol, demo, claims. Read at least §§5, 7, 9–11, 14–15 before architecture-dependent work.
2. `Project/ARCHITECTURE.md` — module boundaries, data model, API surface, non-negotiable invariants.
3. `Project/WORKFLOWS.md` — user/ML transitions, required test scenarios, five-scene demo.
4. `Project/IMPLEMENTATION_PLAN.md` — phase order, exit gates, required reporting.
5. `Project/Tools And product Requirements.md` — zero-cost guardrails, licensing, environment risks.
6. `Project/DESIGN.md` — workbench visual tokens only, never product logic.

Read all of `ARCHITECTURE.md`, `WORKFLOWS.md`, and `IMPLEMENTATION_PLAN.md` before Phase 1. If docs conflict, choose the stricter, local-first, fail-closed reading and record the conflict; never silently pick one.

## 2. Non-negotiables (violating any = stop)

- Scope is Syntax Error 2026 Local LLM Track, **Problem Statement #3** only. Do not add, narrow, or replace product features.
- Local-only: SGLang bound to `127.0.0.1`; no cloud/paid model APIs, keys, subscriptions, hosted inference, telemetry, analytics, or CDN assets. No silent fallback to another engine or version.
- ACL filtering happens **before retrieval** and is rechecked on every citation/source-open. Restricted text never reaches SGLang.
- The model returns source IDs and an exact quote only. The **server** computes canonical character offsets. Ambiguous, duplicate, or unmappable quotes fail closed.
- Evidence states are `SUPPORTED`, `PARTIAL`, `MISSING`, `CONFLICTED`, `STALE`. The server resolves the final state; model output is candidate input only.
- Substring containment is not entailment. Require an independent entailment check for claim-to-quote support.
- Exactly **one** bounded repair for repairable semantic/quote errors. Authorization, ACL, integrity, identity, freshness, and stale-source failures are never repaired.
- Retrieved text is untrusted data. Use explicit `<evidence_chunk ... authority="untrusted_data">` delimiters. The answer model has zero tools.
- Dataset splits are locked before generation. Test/OOD examples and test-derived failure labels never enter curation, training, recovery, or tuning.
- Never fabricate results, metrics, runs, logs, screenshots, or "expected" outputs. Use `TBD` until measured; label targets as targets. The 12 stress-test rounds and judge scorecard are design artifacts until backed by logs.
- Pins: SGLang `0.5.22`, CuratorKIT `1.0.0`, AlignTune `0.1.28`, AuditKIT `1.0.0`, `Qwen/Qwen3-4B-Instruct-2507`. A compatibility failure is a **blocked** report plus a human decision — never a silent pin change.
- Keep SGLang, CuratorKIT, AlignTune, and AuditKIT in separate environments where required. Do not co-install conflicting stacks or `pip install -U` mid-run.
- CuratorKIT (LSAL v1.1) and AuditKIT (LSAL v1.2) are source-available, **not** OSI open source or commercially cleared. Preserve `THIRD_PARTY_NOTICES.md`; do not imply commercial rights.
- The spec files are not status. Report progress only in `Project/IMPLEMENTATION_STATUS.md`; never rewrite specs to claim success.

## 3. Target stack and layout

- Python 3.11+, `uv`, pytest. Workbench: thin local UI (Gradio Blocks and/or PDF.js) over application services. SQLite for metadata; start with BM25/FTS5; add FAISS only if the dependency is available.
- Suggested layout under `Project/`: `pyproject.toml`, `uv.lock`, `configs/`, `src/hallx/{api,auth,corpus,ingestion,retrieval,prompting,inference,validation,source_map,diagnostics,escalation,curation,training,evaluation,lineage,workbench}`, `tests/{unit,integration,security,evaluation}`, `scripts/`, `data/`, `checkpoints/`, `results/`, `reports/`.
- Business rules live in services, never in UI callbacks. Reviewer mode never renders unchecked raw output as verified; raw/training internals belong to ML Auditor mode and stay access-controlled.
- UI uses `DESIGN.md` tokens: ink `#17191c`, paper `#ffffff`, mist `#f2f2f3`, peach `#fbe1d1`, sienna `#5d2a1a`; 24px cards, pill buttons, 1200px max width. Signifier/Sohne are not bundled; use the documented substitutes (Source Serif 4/Georgia, Inter/system-ui), self-host, and add no font CDN.
- PDF highlighting uses server-generated offsets. If the parser cannot prove a mapping, show an explicit "unsupported mapping" state; never fake a highlight.

## 4. Commands (target — fail until Phase 1 scaffold exists)

Do not claim a command passed unless it actually ran. Today `uv sync --frozen` fails because there is no `uv.lock`.

```powershell
uv sync --frozen
uv run pytest -q
uv run pytest tests/unit/test_span_verifier.py -q
uv run pytest -q -k "acl and not slow"
uv run pytest -m "not slow"
uv run python -m hallx.workbench.app --sglang-url http://127.0.0.1:30000 --port 7860
curl.exe http://127.0.0.1:30000/v1/models
curl.exe http://127.0.0.1:7860/api/health
```

- PowerShell: use `curl.exe`, not `curl` (alias to `Invoke-WebRequest`). Use `uv run python`, not `python3`.
- SGLang launch: follow `IDEA.md` §15, bind `127.0.0.1:30000`, keep `--grammar-backend xgrammar`. Do not add `--enable-lora-overlap-loading` without a benchmark.
- No GPU on this host: run Phase 3/5 only on free Colab/Kaggle per the Tools doc, or mark **blocked**. Do not install the full SGLang stack locally "just to try".
- Add `ruff`/`mypy` only if the scaffold includes them; do not invent tool configs mid-phase.

## 5. Phase protocol (mandatory)

### 5.1 Contract first

Before any code, the orchestrator writes `Project/reports/contracts/P<N>-<slug>.md` containing:

- objective and explicit in/out of scope;
- disjoint write paths per worker;
- frozen interfaces: schemas, function signatures, route shapes, DB columns, error codes, state transitions;
- exact acceptance commands and pass criteria;
- invariants that must have tests;
- stop/blocked conditions.

Any contract change is a version bump; notify every worker. Never silently edit an interface another agent owns. If an interface is missing or ambiguous, stop and report — do not invent a second source of truth.

Contract template:

```text
# P<N> — <slug> contract v1
OWNER: <orchestrator>
OBJECTIVE: <user-visible outcome>
IN SCOPE: <bullets>
OUT OF SCOPE: <bullets>
FROZEN INTERFACES: <schemas, signatures, routes, DB columns, error codes, states>
WRITE PATHS: <worker role> -> <exact paths>
ACCEPTANCE: <command> -> <pass criteria>
INVARIANTS/TESTS: <invariant> -> <test id>
EVIDENCE: <log/api/browser paths>
STOP/BLOCKED: <conditions that require a human decision>
CHANGES: v1 initial
```

### 5.2 Master phase prompt (copy, fill, give to every subagent)

```text
You are the <role> for <phase> of HallX-Local.

MISSION: <one paragraph, user-visible outcome>
READ FIRST: <contract path + spec sections>
FROZEN CONTRACT: <path> vN. Do not change it.
WRITE SCOPE: only <paths>. Never edit <paths>.
STEPS: 1) ... 2) ... 3) ...
INVARIANTS: <what must remain true; cite spec lines>
ACCEPTANCE: run <exact commands>; pass = <exact criteria>
EVIDENCE: return exact command, exit code, key output; save logs/screenshots to <paths>
STOP: if <condition>, stop and return BLOCKED with the full error; do not guess.
FORBIDDEN: scope changes, external APIs, fabricated outputs, git commits (the orchestrator commits per §5.6),
editing specs, touching locked test/OOD splits, editing files outside WRITE SCOPE.
REPORT: STATUS | CHANGED | COMMANDS+RESULTS | TESTS | EVIDENCE | BLOCKED | NEXT
```

### 5.3 Subagent rules

- Use `explore` for read-only reconnaissance; `general` for writers, verifiers, and runners. Unless marked `explore`, every role below runs as `general`; the names are prompt personas, not new agent types.
- Cap concurrent writers at 4 and total subagents at 6 per phase. More adds merge risk without speed.
- Two agents may edit the same interface only through a contract version bump. Never let two writers touch one file.
- Recon agents never edit. Test writers may work in parallel with implementers only against the frozen contract.
- The orchestrator owns merges, contract changes, the final gate, and `IMPLEMENTATION_STATUS.md`.
- If a delegated agent lacks Chrome DevTools tools, it returns the URL and exact steps; the orchestrator runs the browser gate. Never mark a browser gate passed without evidence.
- Reuse a subagent session (`task_id`) for fixes in its own scope; use a fresh agent for independent verification.

### 5.4 Parallel scheduling

| Wave | Runs in parallel | Notes |
|---|---|---|
| W0 | Phase 0 | Recon agents only; no edits outside status/reports. |
| W1 | Phase 1 | Freeze contract, then split schema, canonicalization, validators, tests. |
| W2 | Phase 2 + Phase 3a (adapter skeleton) + Phase 4a (UI shell) | All may start after Phase 1 contracts freeze. |
| W3 | Phase 3b (integration) + Phase 4b (wiring) + Phase 6a (scorers with fixtures) | 3b waits for Phase 2 evidence bundle. |
| W4 | Phase 5 (GPU stages, serialized) + Phase 7a (auditor shell, CPU) | Never train and serve simultaneously without measured VRAM proof. |
| W5 | Phase 6b (final evaluation) + Phase 7b (demo) | 6b waits for Phase 5 artifacts. |
| W6 | Full regression + browser + security + docs gate | No new scope. |

Parallelize only when write scopes are disjoint, contracts are frozen, and no shared GPU/server is involved. Serialize: SGLang launches, GPU training, DB migrations, shared fixture edits, contract changes. Use a lock file or explicit owner for the GPU.

### 5.5 Phase kickoff checklist

1. Write and freeze the phase contract; create the report/evidence directories.
2. Spawn `explore` recon only if the contract depends on unknown repo state.
3. Spawn writers in parallel, each with the master prompt and its own write scope.
4. Collect reports; reject any report without exact commands and outputs.
5. Run the fast gate, then the phase gate in §7.
6. Write `reports/phase-<N>.md`; update `IMPLEMENTATION_STATUS.md`; commit them with explicit paths per §5.6.
7. Declare the next wave unblocked only if the gate is green and evidence is saved.

### 5.6 Commit cadence (mandatory)

Commit more than once per phase; do not batch a whole phase into one commit. The orchestrator is the only committer — subagents return diffs and evidence.

- **Phase start:** commit the frozen contract and report skeleton.
- **Each coherent sub-step or worker handoff:** commit only that worker's verified files with explicit paths.
- **Phase gate:** commit the final verified state as `phase <N>: <summary>`.
- **Partial/blocked work:** commit as `phase <N>: partial - <scope>` or `phase <N>: blocked - <reason>`; never label unverified work as verified.

Rules:

- First run `git rev-parse --show-toplevel`. If the root is the enclosing home directory or contains unrelated projects, stop and ask the user to initialize or choose a dedicated HallX/Project repo. Never commit HallX into the enclosing home repo.
- Stage explicit paths only: `git add -- <paths>`. Never `git add -A`, `git add .`, or `git commit -am`.
- Before committing, inspect `git diff --cached --stat` and `git diff --cached`. Ensure no unrelated home-directory files, secrets, restricted documents, generated data, checkpoints, or logs containing restricted text.
- Commit message body includes the exact test command and result, e.g. `tests: uv run pytest tests/unit -q -> 42 passed`.
- Do not push, force-push, rewrite history, or change remotes unless the user explicitly asks.
- If the gate is red, commit only the contract/report/diagnostic updates needed to resume; keep the `partial`/`blocked` label.

## 6. Phase map: steps, subagents, gates

### Phase 0 — Repository and environment audit

- Steps: inventory docs/git/env; confirm or initialize the dedicated HallX/Project repo (ask before creating a new repo; never commit into the home repo); probe Python, uv, CUDA, GPU, disk, network; attempt baseline tests; write `IMPLEMENTATION_STATUS.md` and `reports/phase-0.md`.
- Subagents: 3 `explore` recon agents (scope/invariants, workflows/UI scenarios, environment/tooling), 1 synthesizer, 1 verifier.
- Gate: no edits outside status/reports; every capability marked `implemented`/`tested`/`blocked`/`planned`; absent tests are "not run", not "pass"; blockers recorded with exact diagnostics.
- Parallel: the three recon agents.

### Phase 1 — Contracts and deterministic core

- Steps: freeze contract v1 (package `hallx`, models, generation-time vs final `ProofEnvelope`, error codes, canonicalization version, source-map API); implement schema/models; canonical text + source maps; unique-quote resolver; numeric/version/ACL/status checks; five-state resolver; unit/security tests.
- Subagents: contract architect, schema/models, canonicalization/source-map, validators/resolver, test writer, verifier.
- Parallel: schema and canonicalization after contract; validators after both; tests drafted against the contract in parallel.
- Gate: `uv run pytest` succeeds without GPU or live LLM; all nine cases pass (supported, partial, missing, conflicted, stale, duplicate quote, numeric mismatch, access denial, injected text); no model-supplied offset path; ambiguity fails closed.
- Produces: `configs/proof_envelope_schema.json`, core tests, contract record.

### Phase 2 — Local corpus and retrieval

- Steps: documents/versions/ACL; ingestion, extraction, chunking, hashes, page maps; pre-retrieval ACL + BM25-first hybrid retrieval; separate stale diagnostic path; active-version precedence and conflict pairs; frozen snapshot/splits + leakage checks; tests.
- Subagents: corpus/versions, ingestion/source maps, retrieval/ACL, splits/leakage, security tests, verifier.
- Parallel: corpus, ingestion, and retrieval after Phase 1 interfaces; may overlap Phase 3a and Phase 4a.
- Gate: deterministic evidence bundle with trace and permissions before any SGLang call; `test_acl_filtering` and `test_split_leakage` pass; revoked ACL, cross-workspace IDs, superseded versions, cache invalidation, duplicate families covered.
- Dense retrieval is optional; do not make FAISS a gate.

### Phase 3 — SGLang inference integration

- Steps: thin adapter (health, structured generation, registry, timing, failure capture); prompt builder with prefix-stable ordering and untrusted delimiters; orchestration with validator + one repair; toy-corpus smoke; malformed/truncated handling; no fallback.
- Subagents: adapter, prompt/orchestration, failure/repair tests, runtime verifier (GPU/server owner).
- Parallel: adapter and prompt work may start with Phase 2; full integration waits for the Phase 2 evidence bundle.
- Gate: loopback-only end-to-end answer on a toy corpus; schema-constrained request; measured stage timings and audit trace; `test_prompt_injection`; if pinned SGLang cannot run, return **blocked** — do not switch engines.
- Do not enable the four-adapter arena until per-request adapter selection is tested.

### Phase 4 — Reviewer workbench

- Steps: shell/nav with design tokens; Adjudicate → Evidence Run Detail → Source Inspector; Documents → Version History; Evidence Runs; Escalations with audit events; reviewer/auditor access separation; PDF highlight from server offsets or explicit unsupported state.
- Subagents: shell/tokens, reviewer flows, source viewer/PDF, accessibility/design reviewer, browser verifier.
- Parallel: shell after Phase 1; wiring after Phase 3; CPU work may overlap Phase 5.
- Gate: Chrome DevTools E2E for answerable, missing, conflicted, and stale cases; zero uncaught console errors; no external network requests; screenshots saved; wrong-highlight test; reviewer never sees raw output as verified.
- Unreliable source mapping = show unsupported, never fake.

### Phase 5 — Curation and training orchestration

- Steps: verify licenses/versions; separate CuratorKIT jobs for raw and curated exports (and per task: QA/RAFT, DPO, GRPO); validate token parity/provenance/checksums; `aligntune advise` + config validation; M1 SFT/RAFT → M2 DPO → M3 Dr. GRPO sequentially; reward tests; persist every stage.
- Subagents: curation config/runner, dataset validator, training runner (holds GPU lock), reward/tests, verifier.
- Parallel: CPU-side validation and reward tests only; GPU jobs are serialized. Never run training and serving together without measured VRAM proof.
- Gate: configs, logs, adapters, hashes, and parent checkpoints exist; only completed stages marked complete; `test_verifiable_rewards`; quota-blocked stages stay resumable and incomplete; no fabricated four-way comparison.
- Keep generator and judge endpoints genuinely separate; never route both model names to one server.

### Phase 6 — AuditKIT evaluation and feedback loop

- Steps: deterministic scorers with direction contracts; matched pre-gate vs post-gate comparisons; per-sample + unscored cases + fingerprints + uncertainty; verify resampling unit; feedback guard (test/OOD never enters recovery); self-contained audit bundle with checksums.
- Subagents: scorers, evaluation runner, feedback-guard tests, verifier.
- Parallel: scorer/guard code with fixtures during Phase 5; final evaluation after Phase 5 artifacts.
- Gate: every metric traceable to a frozen dataset/model/config; `test_closed_loop`; test split untouched; model-only and system-gate metrics reported separately; audit bundle reproducible.

### Phase 7 — ML Auditor workbench and demo readiness

- Steps: auditor screens; five-scene demo with real captured outputs; failure-mode tests (startup, missing adapter/GPU, incompatibility, lineage mismatch, unauthorized source, repair exhaustion); exposure check; `README.md`, `LIMITATIONS.md`, `THIRD_PARTY_NOTICES.md`, reproduction commands, unrun-experiment list.
- Subagents: auditor UI, demo runner, failure/security tests, browser/network verifier, docs writer.
- Parallel: auditor shell with clearly labeled fixtures earlier; final demo is last and sequential.
- Gate: all five scenes use real outputs; no placeholder or replay presented as live; browser + network gate passes; docs complete; status honest.

## 7. Verification gates

### 7.1 Fast gate (after every subagent task)

- Focused tests for the touched module.
- Run the scaffold's lint/typecheck if configured; do not invent a tool config mid-phase.
- Import/smoke of the changed entrypoint.
- If UI touched: no new console errors and no external requests.
- Return exact command, exit code, and key output. "Looks good" is not evidence.
- Done means the contract's acceptance commands pass and evidence is saved; code existing is not done.

### 7.2 Phase gate (orchestrator, mandatory)

1. `uv run pytest tests/unit -q` or the phase's focused suites.
2. Phase-specific invariant/security tests.
3. `uv run pytest -q` (mark expensive tests `slow`; still run before the final gate).
4. API smoke with `curl.exe` against loopback.
5. Browser E2E with Chrome DevTools.
6. Save evidence. On failure: fix or mark **blocked**; never proceed on a red gate.

### 7.3 Chrome DevTools recipe (all UI phases)

Use the `chrome-devtools` MCP tools:

1. `list_pages`; `navigate_page` to the workbench URL (or `new_page`); wait for load.
2. `take_snapshot`; interact using `click`, `fill_form`, `type_text`, `press_key` with snapshot `uid`s.
3. `wait_for` the expected state; `take_snapshot` again.
4. `list_console_messages` filtered to `error`/`warn`: zero uncaught errors; record anything else.
5. `list_network_requests`: only `127.0.0.1`/`localhost`; no external model, font, CDN, or analytics calls; inspect failed XHR/fetch with `get_network_request`.
6. `take_screenshot` to `Project/reports/evidence/p<N>/<case>.png`.
7. Run the phase's required cases: answerable, missing, conflicted, stale, unauthorized, injection (as applicable).

A screenshot alone is not proof. Assert visible text/state and record console/network evidence. For Gradio shadow DOM, rely on the accessibility snapshot; use `evaluate_script` read-only for inspection, never to fake state. If Chrome/browser tools are unavailable, mark the browser gate **blocked** and fall back to `curl.exe` + server logs; never call it passed.

### 7.4 Backend and security checks

- Revoke an ACL after a query: new request and source-open must recheck; no unsafe cached result.
- Guess a restricted chunk ID: it must never reach SGLang (assert from request logs).
- Inject a prompt-injection payload into a chunk: treated as data, no tool call, correct state.
- Duplicate quote: fail closed. Numeric/unit mismatch: fail. One repair max; second invalid → abstain.
- Stale source cannot yield `SUPPORTED`; unresolved active conflict yields `CONFLICTED` with both spans.
- Confirm no outbound traffic except loopback. Save redacted request/response pairs.

### 7.5 Evidence layout

```text
Project/reports/
  contracts/P<N>-<slug>.md
  phase-<N>.md
  evidence/p<N>/{logs,api,browser}/
```

Each record: command, exit code, timestamp, working-tree state, commit SHA, environment/package versions, GPU if used, artifact SHA-256. No secrets or restricted document text in reports.

## 8. End-of-phase output (exact format)

Return exactly this block, then update `Project/IMPLEMENTATION_STATUS.md` and commit per §5.6:

```text
PHASE: P<N> <name>
STATUS: verified | partial | blocked
CONTRACT: <path> vN
CHANGED: <paths>
COMMIT: <sha> <message>
COMMANDS:
- <command> -> exit <code>: <key output>
TESTS: <passed>/<failed>/<skipped>; invariants: <test ids>
BROWSER: <url>; cases: <list>; console errors: <n>; external requests: <n>; screenshots: <paths>
ARTIFACTS: <path> sha256=<...>
BLOCKED/NOT PROVEN: <exact>
NEXT: <phase> unblocked? yes/no + why
```

`IMPLEMENTATION_STATUS.md` uses the plan's exact words: `implemented`, `tested`, `blocked`, `planned`. Include commands actually run, hardware, versions/hashes, known failures, licensing concerns, and the next exit gate. If a test was not run, write "not run"; if a stage did not complete, write "blocked/incomplete".

## 9. Quality bar

- Every bug fix and invariant gets a failing test first, then a passing test.
- Failure paths are first-class: denied, stale, duplicate, malformed, timeout, OOM, missing artifact.
- Deterministic fixtures/seeds; unit tests do not touch the network.
- No stubs or TODOs in paths claimed complete; no silent exception swallowing; fail closed with typed errors.
- UI covers empty/loading/error/unsupported states, keyboard focus, and the DESIGN.md tokens.
- Performance is measured, not claimed; label target vs measured; include p50/p95 and hardware.
- Docs stay reproducible: one-command run, limitations, third-party notices, unrun experiments.

## 10. Repo-specific gotchas

- Docs-only today: scaffold commands will fail until Phase 1 creates `pyproject.toml` and `uv.lock`.
- Enclosing home-directory git repo: never stage broadly; `HallX/` is not tracked.
- Windows: `curl` is an alias; use `curl.exe`. `python3` is absent; use `uv run python`.
- No local GPU: `nvidia-smi` missing. Do not install SGLang locally; use free cloud runtimes or block.
- SGLang install docs mention CUDA 13 while `IDEA.md` assumes CUDA 12.4; smoke-test the real runtime first and record the exact blocker.
- Separate environments: SGLang, CuratorKIT, AlignTune, and AuditKIT can conflict; evaluate served SGLang over HTTP rather than co-installing it.
- `curatorkit[all]` excludes the `pdf` extra; MinerU is AGPL-3.0. Start with `pdfplumber`.
- AuditKIT upstream may be newer (e.g. 1.1.3) than the pinned 1.0.0; verify the API before use.
- Signifier/Sohne are not bundled; use the documented substitutes and self-host. No CDN loads in a local-first app.
- Do not reproduce the 12 stress-test rounds or scorecard as executed evidence until logs exist.

## 11. Stop and ask

Ask before: changing pins/toolchain/package name/scope; using any paid or hosted resource; destructive migrations or deleting data/checkpoints/artifacts; resolving a spec contradiction that changes behavior; exposing restricted data or enabling external calls; pushing, rewriting history, changing remotes, or committing when the project repo is ambiguous.
