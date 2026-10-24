# HallX-Local — Agent Implementation Plan (10 phases)

**Status:** Execution plan v2. `IDEA.md` is the product/research source of truth; `ARCHITECTURE.md` owns module boundaries; `WORKFLOWS.md` owns user/ML transitions. This file orders execution and defines gates; it is not evidence that a phase has run. Report actual status only in `IMPLEMENTATION_STATUS.md` and `reports/phase-<N>.md`.

**Phase count:** 10 numbered phases, `Phase 0` through `Phase 9`. The previous 8-phase draft is mapped at the end. A phase is complete only when its gate commands have actually run and the evidence is saved.

---

## 0. Plan-wide non-negotiables

These bind every phase. Violating one is a stop condition, not a trade-off.

1. Scope is **Syntax Error 2026 Local LLM Track, Problem Statement #3** only.
2. Local-only: SGLang bound to `127.0.0.1`; no cloud/paid model APIs, keys, telemetry, analytics, CDN assets, or silent engine fallback.
3. ACL filtering happens **before retrieval** and is rechecked on every citation/source-open. Restricted text never reaches SGLang.
4. The model returns source IDs and an exact quote only. The **server** computes canonical character offsets. Ambiguous, duplicate, or unmappable quotes fail closed.
5. Evidence states are `SUPPORTED`, `PARTIAL`, `MISSING`, `CONFLICTED`, `STALE`. The server resolves the final state; model output is candidate input only.
6. Substring containment is not entailment. An independent entailment check is required for claim-to-quote support.
7. Exactly **one** bounded repair for repairable semantic/quote errors. Authorization, ACL, integrity, identity, freshness, and stale-source failures are never repaired.
8. Retrieved text is untrusted data. Use explicit `<evidence_chunk ... authority="untrusted_data">` delimiters. The answer model has zero tools.
9. Dataset splits are locked before generation. Test/OOD examples and test-derived failure labels never enter curation, training, recovery, or tuning.
10. Never fabricate results, metrics, runs, logs, screenshots, or expected outputs. Use `TBD` until measured; label targets as targets.
11. Pins: SGLang `0.5.22`, CuratorKIT `1.0.0`, AlignTune `0.1.28`, AuditKIT `1.0.0`, `Qwen/Qwen3-4B-Instruct-2507`. A compatibility failure is a **blocked** report plus a human decision, never a silent pin change.
12. Keep SGLang, CuratorKIT, AlignTune, and AuditKIT in separate environments where required. No co-installing conflicting stacks and no `pip install -U` mid-run.
13. CuratorKIT (LSAL v1.1) and AuditKIT (LSAL v1.2) are source-available, **not** OSI open source or commercially cleared. Preserve `THIRD_PARTY_NOTICES.md`.
14. The spec files are not status. Do not rewrite specs to claim success.

---

## 1. Grandmaster operating doctrine

The plan is played like a long game: secure the position before attacking, keep a reserve, and never stake the submission on one unverified run.

1. **Contract before code.** No phase writes architecture-dependent code before its contract is frozen in `reports/contracts/`. Interfaces are versioned; a change is a version bump with a note to every worker.
2. **Tempo through vertical slices.** Each phase lands the smallest end-to-end slice that proves its thesis, then widens. A beautiful module that cannot be exercised is not progress.
3. **Prophylaxis before treatment.** Security, ACL, freshness, and integrity tests are written with the feature, not after it. Fail closed by default; every exception is typed and tested.
4. **Maintain a reserve.** Keep one working checkpoint, one green test suite, and one reproducible demo path at all times. Never risk the last working state on an unmeasured experiment.
5. **Falsify, don't decorate.** Every claim needs a command, an exit code, and an artifact. Targets stay targets. A red gate is a stop, not a footnote.
6. **No tempo loss to scope drift.** Do not add product features, dashboards, connectors, or "just one more model" during a phase. Park ideas in the phase report.
7. **Respect the board.** Critical path is `P1 -> P2 -> P3 -> P4 -> P5` for the product and `P2 -> P6 -> P7 -> P8` for the ML loop; `P9` consumes both. CPU-only work may run in parallel only where write paths are disjoint.
8. **Endgame is a gate, not a demo.** The demo is the last phase because it consumes verified artifacts; it never substitutes for them. A recorded replay must be labeled as recorded.

---

## 2. Phase map

| Phase | Mission | Primary artifact | Gate (short form) | Owns the failure of |
|---|---|---|---|---|
| **0** | Repository, environment, and compliance baseline | `IMPLEMENTATION_STATUS.md`, `reports/phase-0.md` | Audit is honest; blockers exact; no unauthorized edits | Wrong repo, hidden GPU/dependency assumption |
| **1** | Contracts and deterministic core | Package scaffold, models, schema, canonicalizer, validators, unit tests | `uv run pytest tests/unit -q` green without GPU/LLM | Model-owned offsets, ambiguous quotes, state drift |
| **2** | Corpus registry, versions, ACL policy | SQLite schema + registry + snapshot API + tests | Revocation, cross-workspace, supersession, integrity tests green | Unauthorized or stale evidence entering the pipeline |
| **3** | Ingestion, source maps, ACL-first retrieval | Ingested toy corpus, page maps, FTS5/BM25 index, frozen bundle trace | Deterministic bundle + trace + split leakage tests green | Unprovable highlights, retrieval leaks, split contamination |
| **4** | SGLang inference integration and bounded orchestration | Loopback adapter, prompt builder, one-repair orchestration, smoke run | Loopback E2E on toy corpus + injection test + measured timings | Silent fallback, malformed generation, unbounded repair |
| **5** | Reviewer workbench | Adjudicate / Runs / Documents / Escalations / Source Inspector | Chrome DevTools E2E for 4 states, zero external requests, screenshots | Unverified output shown as verified, fake highlights |
| **6** | CuratorKIT curation orchestration | Per-task curation configs, exports, provenance, rejection artifacts | Version/licence verified, token parity, provenance/checksum checks | Poisoned data, leakage into training, unlicensed use |
| **7** | AlignTune progressive training | M1 DA-RAFT -> M2 DPO -> M3 Dr. GRPO adapters + reward tests | `aligntune advise` + config validation + reward bounds + lineage | Destroying a working checkpoint, reward hacking, lazy abstention |
| **8** | AuditKIT evaluation and feedback loop | Frozen evaluation suite, pre/post metrics, audit bundle | Model-only vs system metrics separated, feedback guard green | Test-set contamination, untraceable metrics |
| **9** | ML Auditor workbench, demo, release gate | Auditor screens, five real scenes, failure-mode tests, docs | Browser/network gate + real outputs + honest docs | Shipping a replay or unmeasured claim as evidence |

---

## 3. Phase 0 — Repository, environment, and compliance baseline

**Mission:** Establish where work lives, what the host can actually do, and which mandatory claims are blocked before anyone writes architecture-dependent code.

**Entry:** Access to `Project/` and the host shell.

**Workstreams (read-only except reports/status):**
1. Inventory files, git root/status/remotes, Python/uv/Node versions, disk, GPU, CUDA, network posture.
2. Confirm or initialize a dedicated HallX repo. Never commit `HallX/` into the enclosing home repository. Ask the user before creating a repo.
3. Attempt baseline commands (`uv sync --frozen`, `uv run pytest`) and record the exact failure when the scaffold is absent.
4. Write `IMPLEMENTATION_STATUS.md` with every capability marked `implemented`, `tested`, `blocked`, or `planned`.
5. Write `reports/phase-0.md` with commands, exit codes, environment facts, and the repo decision.

**Frozen artifact:** `Project/reports/contracts/P0-baseline.md` (or the status/report pair if no contract is needed).

**Exit gate:**
- `git rev-parse --show-toplevel` recorded; repo ambiguity resolved or explicitly blocked.
- `python --version`, `uv --version`, `nvidia-smi` result, disk free, and package availability recorded.
- Baseline test attempt recorded as "not run" or the exact failure; never "pass".
- No edits outside `IMPLEMENTATION_STATUS.md`, `reports/`.

**Stop conditions:** Git root is the home directory and no dedicated repo exists; missing write access; undisclosed paid/cloud resource required.

**Countermove:** If the repo is ambiguous, keep coding local and defer commits; record `blocked: commit` until the user chooses.

---

## 4. Phase 1 — Contracts and deterministic core

**Mission:** Make the truth boundary executable: a model candidate can be parsed, checked, and either validated or rejected without a GPU, a live LLM, or trust in model-supplied offsets.

**Entry:** Phase 0 facts recorded (repo ambiguity may remain a commit blocker, not a code blocker).

**Frozen contract:** `reports/contracts/P1-contracts-and-deterministic-core.md` v1. It must freeze:
- generation-time and validated `ProofEnvelope` schemas and field names;
- canonicalization version and hash behavior;
- unique-quote resolver API and failure codes;
- numeric/unit comparison rules;
- source identity, status, freshness, and ACL checks;
- five-state resolution inputs, precedence, and outputs;
- validation outcome, issue codes, and repair eligibility;
- module write paths and test IDs.

**Workstreams (disjoint write paths):**
1. **Scaffold:** `Project/pyproject.toml`, `Project/uv.lock`, `Project/src/hallx/__init__.py`, `Project/configs/proof_envelope_schema.json`, `Project/configs/track_manifest.yaml`.
2. **Models and errors:** `src/hallx/models.py`, `src/hallx/errors.py` — `Document`, `DocumentVersion`, `Chunk`, `CorpusSnapshot`, `EvidenceBundle`, generation/validated envelopes, typed issue codes.
3. **Canonicalization and source maps:** `src/hallx/canonical.py`, `src/hallx/source_map.py` — Unicode canonicalization, whitespace collapse with explicit mapping, SHA-256, forward/reverse span mapping, unsupported-map failure.
4. **Deterministic validators:** `src/hallx/validation/span.py`, `numeric.py`, `evidence.py`, `state.py`, `envelope.py` — unique quote, numeric/unit, source identity/status/freshness/ACL, five-state resolver, cross-field consistency.
5. **Tests:** `tests/unit/test_*.py` — supported, partial, missing, conflicted, stale, duplicate quote, numeric mismatch, access denial, injected text, plus schema/offset/source-map invariants.

**Hard invariants:**
- Generation schema excludes `char_start` and `char_end`.
- No validator path trusts a model-supplied offset, state, or ACL claim.
- Duplicate/ambiguous quote, unknown chunk, identity mismatch, unauthorized chunk, stale-only support, and unresolved active conflict cannot yield `SUPPORTED`.
- `MISSING` has no factual answer claims; `PARTIAL` names missing information; `CONFLICTED` preserves both references; `STALE` never becomes current support.
- Final `answer_summary` is composed from validated claims and diagnostics, not from unchecked model prose.
- Any security/integrity issue rejects the envelope and is never marked repairable.

**Exit gate:**
```powershell
uv sync --frozen
uv run pytest tests/unit -q
uv run python -c "from hallx.models import GenerationProofEnvelope; print('import-ok')"
```
Pass criteria: install succeeds from the lock; all unit tests pass; the nine required cases exist and pass; no GPU, network, or live LLM is used. If `uv sync` is impossible on the host, record the exact blocker and run the suite with the available interpreter; do not claim the uv command passed.

**Evidence:** command log, exit codes, test list and counts, schema file hash, canonicalization version, commit SHA or `blocked: commit`.

**Stop conditions:** A proposed shortcut places offsets or state authority in model output; an invariant cannot be enforced deterministically; dependency conflict changes the target stack.

---

## 5. Phase 2 — Corpus registry, versions, and ACL policy

**Mission:** Own document identity, immutability, temporal validity, authority, and permissions in one service before any retrieval exists.

**Entry:** Phase 1 models and validators green.

**Frozen contract:** `reports/contracts/P2-corpus-and-acl.md` v1.

**Workstreams:**
1. SQLite schema and migrations for documents, versions, chunks, ACLs, snapshots, audit events.
2. Immutable version creation; supersession links; `effective_from`/`effective_until`; authority and precedence rules.
3. Principal/workspace resolution; role-to-ACL evaluation; deny-by-default policy.
4. Snapshot builder: manifest hashes, chunk hashes, split membership, split-lock hash.
5. Tests: revoked ACL, cross-workspace IDs, superseded version, active conflict, integrity mismatch, snapshot immutability.

**Exit gate:**
```powershell
uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"
```
Pass criteria: ACL is evaluated server-side before any content path; superseded/draft/expired versions cannot be returned as active; the snapshot hash is stable and reproducible; no restricted text appears in errors or logs.

**Stop conditions:** ACL stored only in UI/session; version mutation in place; snapshot hash not reproducible.

---

## 6. Phase 3 — Ingestion, canonical source maps, and ACL-first retrieval

**Mission:** Turn lawful local files into immutable, hash-verified chunks with provable page/range maps, then retrieve only authorized active evidence.

**Entry:** Phase 2 registry and ACL service.

**Frozen contract:** `reports/contracts/P3-ingestion-retrieval.md` v1.

**Workstreams:**
1. PDF/text extraction with `pdfplumber` first; store source hash, canonical text, page/text-run geometry, unsupported-map state.
2. Chunking with stable IDs and canonical ranges; recompute hash; reject unprovable mappings.
3. BM25/FTS5 sparse index; optional dense index only if the dependency is available; pre-retrieval ACL filter.
4. Separate stale-candidate diagnostic path; active-version precedence; conflict pair creation.
5. Frozen evidence bundle with retrieval trace and snapshot hash.
6. Split freeze and leakage tests (family and near-duplicate).
7. Tests: revoked ACL, guessed restricted chunk ID, cache invalidation, superseded version, duplicate family, unmappable PDF range.

**Exit gate:**
```powershell
uv run pytest -q -k "acl and not slow"
uv run pytest -q -k "split_leakage or source_map or retrieval"
```
Pass criteria: a query returns a deterministic bundle + trace + permissions before any SGLang call; restricted chunks never enter the bundle; the test/OOD split hash is locked.

**Stop conditions:** A highlight is synthesized without a source map; retrieval ranks before ACL filtering; split membership changes after synthesis starts.

---

## 7. Phase 4 — SGLang inference integration and bounded orchestration

**Mission:** Prove the loopback answer path with the pinned engine, structured generation, server validation, and at most one repair.

**Entry:** Phase 3 deterministic bundle; a free GPU runtime per the Tools doc, or an explicit blocked decision.

**Frozen contract:** `reports/contracts/P4-inference.md` v1.

**Workstreams:**
1. Thin SGLang adapter: health, `/v1/chat/completions` or `/generate`, schema-constrained request, registry, timings, failure capture, no fallback.
2. Prefix-stable prompt builder with explicit `<evidence_chunk authority="untrusted_data">` delimiters; answer model has zero tools.
3. Orchestration: parse, validate, one bounded repair for repairable quote/semantic errors, safe abstention, audit trace.
4. Toy-corpus smoke: supported, missing, conflicted, stale, injection, malformed/truncated.
5. Runtime diagnostics: model/adapters, schema smoke, loopback binding, cache metrics.

**Exit gate:**
```powershell
curl.exe http://127.0.0.1:30000/v1/models
uv run pytest -q -k "inference or prompt_injection or repair"
```
Pass criteria: one complete schema-constrained answer path on a toy corpus; measured stage timings; injected text treated as data; one-repair maximum; authorization/ACL failures never repaired. If pinned SGLang cannot run, mark **blocked** and stop.

**Stop conditions:** Another engine is substituted; model offsets are trusted; repair loop exceeds one; restricted text appears in a request log.

---

## 8. Phase 5 — Reviewer workbench

**Mission:** Let a reviewer ask, inspect verified claims, open the exact source span, and escalate without ever seeing unvalidated output as verified.

**Entry:** Phase 4 answer path (or Phase 3 fixtures for shell-only work with explicit labels).

**Frozen contract:** `reports/contracts/P5-workbench.md` v1.

**Workstreams:**
1. Shell/nav with `DESIGN.md` tokens; no business logic in UI callbacks.
2. Adjudicate -> Evidence Run Detail -> Source Inspector.
3. Documents -> Version History.
4. Evidence Runs and Escalations with audit events.
5. Reviewer/auditor access separation; raw output auditor-only.
6. PDF highlight from server offsets or explicit unsupported state.
7. Accessibility: keyboard focus, empty/loading/error states.

**Exit gate (Chrome DevTools):** answerable, missing, conflicted, stale, unauthorized, injection cases; zero uncaught console errors; zero external requests; wrong-highlight test; screenshots saved under `reports/evidence/p5/browser/`.

**Stop conditions:** UI renders raw model prose as verified; a highlight is faked; an external font/CDN request appears.

---

## 9. Phase 6 — CuratorKIT curation orchestration

**Mission:** Produce provenance-gated, token-equalized synthetic training data with auditable rejections and no split leakage.

**Entry:** Phase 2 source units; GPU runtime or blocked decision.

**Frozen contract:** `reports/contracts/P6-curation.md` v1.

**Workstreams:**
1. Verify CuratorKIT `1.0.0`, extras, LSAL v1.1, MinerU AGPL boundary.
2. Separate per-task jobs (`qa`, `cot`, `adversarial_qa`, `adversarial_preference`, `grpo`); separate generator/judge endpoints.
3. Explicit provenance gate, judge, hygiene, embedding dedup, adaptive recovery.
4. Raw ungated and curated/recovered exports with matched token/example budgets.
5. Validate quote containment, provenance, checksums, split membership.
6. Preserve manifests, rejected samples, diagnostic summaries, dataset card.

**Exit gate:** exports + manifests + checksums exist; token parity within stated tolerance; 100% provenance check on accepted samples; no test/OOD source units; no fabricated four-way comparison.

**Stop conditions:** Same model weights used as generator and judge; test data in synthesis; licence terms ignored; raw/curated budgets unmatched.

---

## 10. Phase 7 — AlignTune progressive training

**Mission:** Train in three independently shippable milestones without destroying the last working adapter.

**Entry:** Phase 6 verified exports; GPU lock; `aligntune advise` output.

**Frozen contract:** `reports/contracts/P7-training.md` v1.

**Workstreams:**
1. Verify AlignTune `0.1.28`, backend isolation, config validation.
2. M1 DA-RAFT SFT -> save adapter/logs/config/lineage; evaluate.
3. M2 DPO -> save separately; evaluate.
4. M3 Dr. GRPO with bounded `HallXVerifiableReward`; save; evaluate.
5. Reward tests: bounds, lazy abstention penalty, governance failure, false abstention.
6. Promotion gate: SGLang load smoke + lineage complete.

**Exit gate:** only completed stages marked complete; adapters, logs, hashes, parent checkpoints exist; reward tests pass; a failed/quota-blocked stage remains resumable and incomplete.

**Stop conditions:** Training before profiling; overwriting a checkpoint; claiming a stage ran from a config or notebook; running training and serving concurrently without measured VRAM proof.

---

## 11. Phase 8 — AuditKIT evaluation and feedback loop

**Mission:** Measure model-only and system-gate behavior separately on frozen inputs, with traceable statistics, and feed only train/validation regressions back.

**Entry:** Phase 7 adapters (or baseline artifacts if training is blocked); frozen evaluation suite.

**Frozen contract:** `reports/contracts/P8-evaluation.md` v1.

**Workstreams:**
1. Deterministic scorers with explicit `Direction` contracts.
2. Matched pre-gate vs post-gate comparisons on frozen evidence.
3. Per-sample rows, unscored cases, fingerprints, uncertainty; verify resampling unit.
4. Feedback guard: test/OOD failures recorded but never enter recovery.
5. Self-contained audit bundle with manifests, reports, checksums.

**Exit gate:**
```powershell
uv run pytest -q -k "closed_loop or feedback_guard or scorer"
```
Pass criteria: every metric traceable to frozen dataset/model/config; model-only and system metrics separated; test split untouched; audit bundle reproducible.

**Stop conditions:** Mixing pre/post metrics; test labels in recovery; p-values reported without checking the resampling unit.

---

## 12. Phase 9 — ML Auditor workbench, demo, and release gate

**Mission:** Make the evidence inspectable and the demo honest: real captured outputs, failure modes, lineage, and docs.

**Entry:** Phases 3–8 artifacts that actually exist; no new scope.

**Frozen contract:** `reports/contracts/P9-audit-demo-release.md` v1.

**Workstreams:**
1. Auditor screens: Overview, Corpus & Splits, Curation, Training, Arena, Evaluations, Feedback, Lineage, Runtime Diagnostics.
2. Five-scene demo from `WORKFLOWS.md` using real captured outputs; label any replay.
3. Failure-mode tests: startup, missing adapter/GPU, incompatibility, lineage mismatch, unauthorized source, repair exhaustion.
4. Exposure check: loopback only; demo data only; no unauthenticated private-document path.
5. `README.md`, `LIMITATIONS.md`, `THIRD_PARTY_NOTICES.md`, reproduction commands, unrun experiments.
6. Final regression + browser/network gate.

**Exit gate:** all five scenes trace to logs/artifacts; browser console clean; no external requests; docs complete; `IMPLEMENTATION_STATUS.md` honest; every unrun item labeled `blocked` or `planned`.

**Stop conditions:** A predicted metric, placeholder, or replay is presented as live; a demo scene outruns its evidence; restricted data appears in a report or screenshot.

---

## 13. Critical path, waves, and parallel safety

| Wave | Work | Rule |
|---|---|---|
| W0 | Phase 0 audit | Read-only except status/reports. |
| W1 | Phase 1 contract + scaffold + validators + tests | Freeze contract first; schema/canonicalization in parallel; validators after models. |
| W2 | Phase 2 + Phase 3a (ingestion skeleton) + Phase 4a (adapter skeleton) + Phase 5a (UI shell) | Disjoint write paths; no shared GPU. |
| W3 | Phase 3b (retrieval integration) + Phase 4b (orchestration) + Phase 5b (wiring) + Phase 6a (CPU curation fixtures) | 4b waits for Phase 3 evidence bundle. |
| W4 | Phase 6b (GPU curation) + Phase 7 (serialized training) + Phase 8a (scorers on fixtures) | One GPU owner; never train and serve concurrently without measured VRAM proof. |
| W5 | Phase 8b (final evaluation) + Phase 9a (auditor shell on labeled fixtures) | 8b waits for Phase 7 artifacts. |
| W6 | Phase 9b (demo + full regression + security + browser + docs) | No new scope. |

Serialize: SGLang launches, GPU training, DB migrations, shared fixture edits, contract changes. Cap concurrent writers at 4 and total subagents at 6 per phase. The orchestrator owns contracts, merges, the final gate, and `IMPLEMENTATION_STATUS.md`.

---

## 14. Reporting contract (end of every phase)

Return exactly:

```text
PHASE: P<N> <name>
STATUS: verified | partial | blocked
CONTRACT: <path> vN
CHANGED: <paths>
COMMIT: <sha> <message> | blocked: <reason>
COMMANDS:
- <command> -> exit <code>: <key output>
TESTS: <passed>/<failed>/<skipped>; invariants: <test ids>
BROWSER: <url>; cases: <list>; console errors: <n>; external requests: <n>; screenshots: <paths>
ARTIFACTS: <path> sha256=<...>
BLOCKED/NOT PROVEN: <exact>
NEXT: <phase> unblocked? yes/no + why
```

`IMPLEMENTATION_STATUS.md` uses `implemented`, `tested`, `blocked`, `planned`. If a test was not run, write "not run"; if a stage did not complete, write "blocked/incomplete". No phase report may contain an unlabeled target as a result.

---

## 15. Definition of done (whole project)

The project is done for judging only when:

1. An authorized corpus produces a frozen evidence bundle with trace and permissions.
2. The pinned local SGLang path returns schema-valid output and the server validates it.
3. Every displayed claim has a unique, exact, server-computed span and an independent entailment check.
4. All five evidence states are reachable and tested, including duplicate-quote, numeric, ACL, injection, and repair-exhaustion failures.
5. The reviewer workbench passes browser/network/accessibility gates with no external calls.
6. Any training claims are backed by completed checkpoints, frozen data, and measured evaluation artifacts; uncompleted stages stay `blocked/incomplete`.
7. The audit loop is reproducible from manifests and hashes, and the test/OOD split is provably untouched.
8. Documentation states limitations, licenses, unrun experiments, and reproduction commands without forecast-as-result language.

---

## Appendix A — Mapping from the previous 8-phase draft

| Old phase | New phase(s) |
|---|---|
| 0 — repository and environment audit | 0 |
| 1 — contracts and deterministic core | 1 |
| 2 — local corpus and retrieval | 2 + 3 |
| 3 — SGLang inference integration | 4 |
| 4 — reviewer workbench | 5 |
| 5 — curation and training orchestration | 6 + 7 |
| 6 — AuditKIT evaluation and feedback loop | 8 |
| 7 — ML Auditor workbench and demo readiness | 9 |

No product scope was added, removed, or reordered in a way that changes the thesis; the split exists to make gates, write scopes, and failure ownership unambiguous.
