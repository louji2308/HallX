# HallX-Local implementation status

**Last updated:** 2026-10-24
**Repo root:** `C:\Users\LOUJAN B\HallX`
**Git:** dedicated repository; branch `main`; remote `https://github.com/louji2308/HallX.git`; Phase 1 commits `09e3205`, `28dff15`; Phase 2 implementation `1903f1b`, report/status `a88e484`, pushed. Batch 1 (P3-P6 slices) is uncommitted pending explicit approval.

## Phase status

| Phase | Status | Evidence / note |
|---|---|---|
| P0 Repository and environment audit | `implemented` | Environment inventory and repository isolation complete; formal `reports/phase-0.md` still missing. |
| P1 Contracts and deterministic core | `tested` | `reports/phase-1.md`; 35 unit tests pass; generation schema frozen. |
| P2 Corpus registry, versions, and ACL policy | `tested` | `reports/phase-2.md`; 53-test gate and 87-test full suite pass; Phase 2-scope lint passes; commit `1903f1b`. |
| P3 Ingestion, source maps, ACL-first retrieval | `blocked` | Batch-1 text ingestion + retrieval slices tested (56 focused tests, 222 full suite); PDF page mapping and P2 registry integration not done. |
| P4 SGLang inference and bounded orchestration | `blocked` | Mock-only adapter/prompt/orchestrator tested (37 focused tests); live pinned SGLang smoke blocked by no GPU/server. |
| P5 Reviewer workbench | `blocked` | Fixture shell tested (12 tests); real wiring and Chrome DevTools browser gate not run. |
| P6 Curation validators | `blocked` | Config/provenance/export validators tested (31 tests); real CuratorKIT exports, licence verification, and generation blocked. |
| P7 AlignTune progressive training | `planned` | Not started; no GPU on host. |
| P8 AuditKIT evaluation and feedback loop | `planned` | Not started; needs real P7 artifacts. |
| P9 ML Auditor workbench, demo, release | `planned` | Not started; needs real P3-P8 artifacts. |

## Batch 1 — implemented and tested slices

- **P3A:** deterministic text/Markdown extraction, NFKC canonicalization, stable chunk IDs, canonical/original/page ranges, explicit PDF `SOURCE_MAP_UNSUPPORTED` path; P2 `add_chunk` round-trip test.
- **P3B:** BM25 retrieval only over `registry.authorized_chunks`; strict ACL-before-index; separate `stale_chunks` diagnostic path; deterministic `EvidenceBundle`/`RetrievalTrace`; typed invalid-input failures.
- **P4:** loopback-only SGLang HTTP adapter; typed failures/no fallback; prefix-stable prompt with `<evidence_chunk ... authority="untrusted_data">`; zero tools; exactly one repair; security/ACL/freshness failures never repaired; rejected output has no envelope.
- **P5:** standard-library loopback shell for Adjudicate, Run Detail, Source Inspector, Documents/Versions, Runs, Escalations; DESIGN.md tokens; every fixture clearly labeled; unsupported map not faked; no external URLs/assets.
- **P6:** Pydantic config/provenance/export validators; P2 split vocabulary; five plan configs (`qa`, `cot`, `adversarial_qa`, `adversarial_preference`, `grpo`); separate normalised loopback endpoints; complete split-manifest leakage gate; unique server-computed quotes; pinned checksum; no CuratorKIT import/generation.

## Commands actually run

```powershell
# Phase 1 / Phase 2 (previously verified)
uv run pytest -q                                      # exit 0: 87 passed (Phase 2 baseline)
uv run pytest tests/unit tests/security -q -k "corpus or acl or version or snapshot"  # exit 0: 53 passed

# Batch 1
uv run pytest tests/unit -q -k "ingestion or source_map"           # exit 0: 27 passed
uv run pytest tests/unit tests/security -q -k "retrieval"          # exit 0: 29 passed
uv run pytest tests/unit tests/security -q -k "prompt or inference or orchestration"  # exit 0: 37 passed
uv run pytest tests/unit -q -k "workbench"                         # exit 0: 12 passed
uv run pytest tests/unit -q -k "curation"                          # exit 0: 31 passed
uv run pytest -q                                                   # exit 0: 222 passed in 22.41s
uv run ruff check <all batch-1 source and test paths>              # exit 0: All checks passed!
```

Environment: Python 3.11.9, SQLite 3.45.1, `uv` 0.12.3, pydantic 2.14.1, pytest 8.4.2, ruff 0.16.0, Windows. No GPU used; `nvidia-smi` absent. No SGLang, CuratorKIT, AlignTune, AuditKIT, or network service was run.

## Known failures / blockers

- Batch-1 phase gates are not complete: PDF page mapping, P2 registry ingestion integration, real P5 wiring/browser evidence, and real P6 generation/exports remain open.
- Live SGLang 0.5.22 smoke, real curation/training, and final evaluation require a free GPU runtime or a local GPU; this host has none.
- CuratorKIT 1.0.0 / AuditKIT 1.0.0 source-available LSAL terms and MinerU AGPL-3.0 boundary still require human acceptance before installation/use.
- No real entailment model, tokenizer counts, generated dataset, adapter, checkpoint, evaluation metric, latency, or judge score exists. Fixtures are not execution evidence.
- Repository-wide `uv run ruff check` still reports 21 pre-existing findings in frozen Phase 1 files; batch-1 paths pass.
- `require_train_only(snapshot_id, family_ids)` has no actor parameter; callers must pass a tenant-scoped snapshot.
- `reports/phase-0.md` is still missing.
- Batch 1 is uncommitted; no commit/push was made by workers or orchestrator.

## Licensing

CuratorKIT and AuditKIT have not been installed or used. Preserve `THIRD_PARTY_NOTICES.md`; do not imply commercial rights. MinerU remains an AGPL-3.0 caveat.

## Next exit gate

Batch 2 cannot be described as advancing P4/P6/P7 without a human decision on GPU/Colab/Kaggle access and CuratorKIT/AlignTune licence acceptance. CPU-only P3 PDF/registry integration and P5 browser work can proceed only after that decision is recorded, unless the user explicitly authorizes a CPU-only continuation. The next real gate is a loopback SGLang smoke over an authorized P3 bundle on a GPU runtime, followed by a real P5 browser run.
