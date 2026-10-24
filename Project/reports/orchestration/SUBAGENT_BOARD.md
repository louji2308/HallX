# HallX-Local subagent coordination board

**Updated:** 2026-10-24
**Canonical phase map:** `IMPLEMENTATION_PLAN.md` v2. P3 ingestion/retrieval; P4 SGLang inference; P5 reviewer workbench; P6 curation; P7 training; P8 evaluation; P9 auditor/demo/release.
**Current batch:** 1 complete at slice level; full phase gates not met.
**Commit baseline:** `a88e484` (no batch-1 commit yet)

## Status words

`planned` | `in progress` | `completed` | `blocked` | `needs human`

`completed` requires an exact command, exit code, and saved evidence. A slice may be completed while its whole phase remains `in progress`.

## Batch 1 — independent slices

| Work item | Agent | Status | Write scope | Acceptance |
|---|---|---|---|---|
| P3A ingestion and source maps | `P3A-ingestion` | `completed` | `Project/src/hallx/ingestion/`, `Project/tests/unit/test_ingestion*.py`, `Project/tests/support_ingestion.py`, `Project/reports/evidence/p3/ingestion/` | 27 ingestion/source-map tests, ruff clean; PDF is explicit unsupported, not mapped |
| P3B ACL-first retrieval and bundle trace | `P3B-retrieval` | `completed` | `Project/src/hallx/retrieval/`, `Project/tests/unit/test_retrieval*.py`, `Project/tests/security/test_retrieval_acl.py`, `Project/reports/evidence/p3/retrieval/` | 29 retrieval tests, ruff clean; ACL before index, stale diagnostic-only, deterministic bundle/trace |
| P4 inference and bounded orchestration | `P4-inference` | `completed` (mock-only) | `Project/src/hallx/prompting/`, `Project/src/hallx/inference/`, `Project/src/hallx/orchestration/`, `Project/tests/unit/test_inference*.py`, `Project/tests/unit/test_prompt*.py`, `Project/tests/unit/test_orchestration*.py` | 37 tests, ruff clean; loopback/no-fallback, prompt delimiters, one repair; live SGLang blocked |
| P5 reviewer shell | `P5-workbench` | `completed` (fixture shell) | `Project/src/hallx/workbench/`, `Project/tests/unit/test_workbench*.py` | 12 tests, ruff clean, loopback smoke; browser gate not run; no real data |
| P6 curation validators | `P6-curation` | `completed` (fixture validators) | `Project/src/hallx/curation/`, `Project/configs/curation/`, `Project/tests/unit/test_curation*.py` | 31 tests, ruff clean; five plan configs; no generation, CuratorKIT, or training |

**Batch 1 verification:** `uv run pytest -q` -> exit 0, `222 passed`; batch-scope `uv run ruff check` -> exit 0, `All checks passed!`.

## Phase gate state

| Phase | State | Why the full gate is not met |
|---|---|---|
| P3 | `blocked` | Batch-1 text/retrieval slices tested; PDF page mapping and P2 registry integration pending |
| P4 | `blocked` | Mock slice tested; live pinned SGLang smoke pending GPU/server |
| P5 | `blocked` | Fixture shell tested; real wiring and Chrome DevTools gate pending |
| P6 | `blocked` | Validators tested; CuratorKIT/licence, real exports, and generation pending |
| P7-P9 | `planned` | Not started |

## Future batch queue

| Batch | New independent slice | Continuations |
|---|---|---|
| 2 | P7 training preflight/reward/config with fixtures; GPU jobs blocked | P3 PDF/registry integration, P5 real wiring/browser, P6 manifest/dataset-card validators |
| 3 | P8 deterministic scorers and feedback guard with fixtures; final evaluation blocked | P4/P5 integration, P6/P7 continuation |
| 4 | P9 auditor shell and docs skeleton with labeled fixtures | P5/P6/P7/P8 continuation |
| 5 | none | P9 demo/release gate only after real artifacts exist |

Batch 2 is **not started**. It needs an explicit human decision on GPU/Colab/Kaggle access and CuratorKIT/AlignTune licence acceptance before the phase gates can be credible. CPU-only P3/P5 work could proceed without those decisions, but batch policy says stop and report the dependency rather than imply the blocked stages are advancing.

## Cross-phase flags

| Time | From | Flag | Resolution |
|---|---|---|---|
| 2026-10-24 | P3B | Contract signature allows `snapshot_id=None` while runtime requires non-empty | Typed `RETRIEVAL_SNAPSHOT_INVALID`; P3 integration must pass a real snapshot; no unsafe fallback |
| 2026-10-24 | P4 | Health route and adapter-id source were unspecified | Pinned implementation: `GET /v1/models`; adapter id from top-level or `metadata.adapter_id` |
| 2026-10-24 | P5 | Fixture shell has no Chrome/browser evidence | Browser gate explicitly deferred; not claimed as passed |
| 2026-10-24 | P6 | v1 split/task/checksum/provenance gaps found in read-only audit | Contract **v2** supersedes v1: P2 split names, five plan tasks, complete-manifest leakage, config/snapshot/task identity, exact endpoint/checksum rules |

Agents return flags in their final report with the exact contract/spec line; the orchestrator appends them here. Agents must not overwrite another agent's scope or edit this board directly, to avoid concurrent-write corruption.

## Human dependencies

| Item | Status | Needed from user |
|---|---|---|
| Live SGLang smoke (P4) | `blocked` | Free GPU runtime (Kaggle/Colab or local GPU) able to run pinned SGLang 0.5.22 |
| Real curation/training (P6/P7) | `blocked` | GPU/quota decision and CuratorKIT/AlignTune licence acceptance; no local GPU |
| Final evaluation (P8) | `blocked` | Real P7 artifacts and frozen suite |
| Five-scene demo (P9) | `blocked` | Real P3–P8 artifacts; no placeholder may be presented as live |
| Batch-1 commit/push | `needs human` | Explicit approval for explicit-path commit and push; no commit made by workers |

## Rules

1. Read the phase contract and this board before editing. No contract or spec edits.
2. Write only within the assigned scope. Never touch locked test/OOD splits or P1/P2 frozen files.
3. No cloud/paid APIs, telemetry, CDNs, or silent fallback. SGLang is loopback `127.0.0.1` only.
4. Every finite result needs an exact command and exit code. If not run, report `not run`; never fabricate.
5. One worker may propose a contract change; only the orchestrator bumps the contract version and notifies the batch.
