# P6 — curation configuration, provenance, and export-validation contract v2

OWNER: orchestrator
OBJECTIVE: Build deterministic, fail-closed curation configs and validators so no generated sample can enter training without train-only split provenance, exact unique server-computed quotes, pinned config/snapshot identity, checksums, and genuinely separate loopback generator/judge endpoints.

IN SCOPE (batch 1):
- Pydantic curation config models, loopback/alias normalisation, separate-endpoint/model enforcement.
- Pure provenance and export validation over fixture records.
- Complete split-manifest leakage checks, unique quote/span checks, duplicate checks, token-parity arithmetic, exact checksum validation, and machine-readable issues.
- Five fixture configs matching the plan: `qa`, `cot`, `adversarial_qa`, `adversarial_preference`, `grpo`.
- No generation, CuratorKIT execution/install, AlignTune, datasets, checkpoints, or training claims.

OUT OF SCOPE:
- CuratorKIT/MinerU/AlignTune/SGLang execution or installation, GPU jobs, raw/gated generation, adaptive recovery, embedding dedup, export artifacts.
- Editing P1–P5, specs, lockfiles, or frozen split files.
- Using test/OOD examples or test-derived failure labels in curation/training/recovery.

## FROZEN INTERFACES

Package `hallx.curation`; Pydantic v2, frozen, `extra="forbid"`.

```text
CurationTask(str, Enum): qa, cot, adversarial_qa, adversarial_preference, grpo
RunMode(str, Enum): fixture, live

CurationConfig(run_id:str, mode:RunMode, task:CurationTask, snapshot_id:str,
               split_name:str, generator_endpoint:str, judge_endpoint:str,
               generator_model:str, judge_model:str,
               max_examples:int>0, max_tokens:int>0, seed:int,
               expected_examples:int>0, expected_total_tokens:int>=0,
               token_tolerance:float=0.02, tokenizer_id:str, output_path:str)

SourceRecord(source_id:str, snapshot_id:str, family_id:str,
             split:Literal["train","validation","test_indomain","test_ood_challenge"],
             chunk_id:str, canonical_text:str)

TrainingRecord(sample_id:str, run_id:str, snapshot_id:str,
               config_sha256:hex64, task:CurationTask, source_id:str,
               chunk_id:str, prompt:str, completion:str, quote:str,
               quote_start:int>=0, quote_end:int>quote_start)

CurationIssue(code:str, message:str, sample_id:str|None=None,
              source_id:str|None=None)
ExportValidation(passed:bool, issues:tuple[CurationIssue,...],
                 computed_sha256:hex64, observed_examples:int,
                 observed_total_tokens:int)
```

Required API:

```text
load_config(path:str|Path) -> CurationConfig
config_sha256(config:CurationConfig) -> str
validate_config(config:CurationConfig) -> tuple[CurationIssue,...]
validate_split_manifest(sources:Iterable[SourceRecord]) -> tuple[CurationIssue,...]
export_sha256(records:Iterable[TrainingRecord]) -> str
validate_export(config:CurationConfig, records:Iterable[TrainingRecord],
                sources:Iterable[SourceRecord], *,
                observed_total_tokens:int,
                observed_sha256:str,
                observed_tokenizer_id:str) -> ExportValidation
```

Rules:

### Config and endpoint identity

- `load_config` reads UTF-8 and uses `CurationConfig.model_validate_json`; missing/invalid files propagate `FileNotFoundError`, `json.JSONDecodeError`, or `pydantic.ValidationError` unchanged.
- `validate_config` fails with `SPLIT_NOT_TRAIN` if `split_name != "train"`; `NON_LOOPBACK_ENDPOINT` for any endpoint that is not exactly `http://127.0.0.1:<port>`, `http://localhost:<port>`, or `http://[::1]:<port>`; `GEN_JUDGE_SAME_ENDPOINT` for identical normalised `(host,port)`; `GEN_JUDGE_SAME_MODEL` for identical stripped/casefolded model IDs; `INVALID_BUDGET` for `token_tolerance` not finite/`[0,1]`, `expected_examples > max_examples`, `expected_total_tokens > max_examples * max_tokens`, or defensive non-positive budgets.
- Endpoint parsing uses `urllib.parse.urlsplit`: no credentials, query, fragment, path beyond `/`, or default/absent port; host must be an exact allowlist member (never suffix matching). Normalise `localhost`/`127.0.0.1`/`::1` to a canonical loopback identity plus the explicit port. Different ports are different endpoints; the same port with different model names is still the same endpoint and fails.
- `config_sha256 = sha256(b"hallx.curation.config.v1\n" + canonical_json(config.model_dump(mode="json")).encode("utf-8"))`, where `canonical_json` is `hallx.corpus.snapshot.canonical_json` (`sort_keys=True`, compact separators, `ensure_ascii=False`, `allow_nan=False`).
- Five configs live at `configs/curation/train-{qa,cot,adversarial-qa,adversarial-preference,grpo}.json`; all are `mode="fixture"`, use a fixture snapshot, distinct loopback endpoints 30000/30001, generator pinned to `Qwen/Qwen3-4B-Instruct-2507`, judge model `fixture/independent-judge`, and clearly fixture output paths. They are configuration artifacts, never execution evidence.

### Split/provenance

- `validate_split_manifest` requires at least one `SourceRecord` in each of the four P2 split names; otherwise `SPLIT_MANIFEST_INCOMPLETE`. Duplicate `source_id` -> `DUPLICATE_SOURCE`. The caller must pass the complete manifest; a train-only subset is not evidence and fails the completeness gate.
- For every training record: source must exist -> `UNKNOWN_SOURCE`; source snapshot must equal config snapshot -> `SNAPSHOT_MISMATCH`; source split must be `train` -> `SPLIT_LEAKAGE`; the source family must not appear in `validation`, `test_indomain`, or `test_ood_challenge` -> `SPLIT_LEAKAGE`.
- Record `run_id`, `snapshot_id`, task, `source_id`, and `chunk_id` must match config/source -> `RUN_MISMATCH`, `SNAPSHOT_MISMATCH`, `TASK_MISMATCH`, `UNKNOWN_SOURCE`, `CHUNK_MISMATCH`; `config_sha256` must match -> `CONFIG_MISMATCH`.
- Reject empty IDs/prompt/completion/quote -> `EMPTY_FIELD`; duplicate `sample_id` -> `DUPLICATE_SAMPLE`.

### Quote and export gates

- Quote resolution uses `hallx.validation.span.resolve_unique_quote` on the source `canonical_text`: zero occurrences -> `QUOTE_UNMAPPABLE`; more than one -> `QUOTE_UNMAPPABLE`; span mismatch -> `QUOTE_SPAN_MISMATCH`. `quote_start/end` are server-verified half-open code-point offsets, never trusted candidate offsets.
- `observed_examples == expected_examples` -> else `EXAMPLE_COUNT_MISMATCH`.
- `observed_tokenizer_id == config.tokenizer_id` -> else `TOKENIZER_MISMATCH`.
- Token parity: `abs(observed_total_tokens - expected_total_tokens) / max(expected_total_tokens, 1) <= token_tolerance` -> else `TOKEN_PARITY_FAILED`. Counts are caller-observed fixture/count-sidecar values, not invented tokenization.
- `export_sha256` materialises records once, sorts by `sample_id`, canonical-JSON dumps each record with `sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`, joins with `"\n"`, appends one trailing `"\n"`, prefixes `b"hallx.curation.export.v1\n"`, and SHA-256 hashes the UTF-8 bytes. `observed_sha256` must equal it -> else `CHECKSUM_MISMATCH`.
- Issue order is deterministic: split-manifest issues, config/identity, source/provenance, quote, duplicate, count, tokenizer, parity, checksum. Emit every detected issue; never drop a bad sample silently. `passed = not issues`.
- No CuratorKIT/AuditKIT import, network call, generation, or data write.

## WRITE PATHS

- `Project/src/hallx/curation/`
- `Project/configs/curation/train-qa.json`, `train-cot.json`, `train-adversarial-qa.json`, `train-adversarial-preference.json`, `train-grpo.json`
- `Project/tests/unit/test_curation*.py`, `Project/tests/support_curation.py`
- `Project/reports/evidence/p6/` (validator-only evidence)
- Do not edit P1–P5, specs, lockfiles, frozen splits, or `IMPLEMENTATION_STATUS.md`.

## ACCEPTANCE

```powershell
uv run pytest tests/unit -q -k "curation"
uv run ruff check src/hallx/curation tests/unit/test_curation*.py tests/support_curation.py
uv run python -c "import json; from pathlib import Path; [json.loads(Path(f'configs/curation/train-{n}.json').read_text()) for n in ('qa','cot','adversarial-qa','adversarial-preference','grpo')]; print('configs parse')"
```

Pass criteria: commands exit 0; alias-normalised endpoint separation; non-loopback tricks rejected; incomplete/test/OOD manifests rejected; unique quote/span enforced; duplicates/count/tokenizer/parity/checksum mismatches fail; valid fixture passes; no generation/training claim.

## INVARIANTS / TESTS

- Endpoint alias/model separation -> `test_curation_rejects_shared_generator_judge`.
- Loopback exactness -> `test_curation_rejects_non_loopback`.
- Complete manifest + family leakage -> `test_curation_rejects_test_ood_leakage`.
- Unique server-computed quote -> `test_curation_quote_must_be_unique_and_server_computed`.
- Provenance/config/snapshot/task identity -> `test_curation_provenance_identity_failures`.
- Duplicate sample/source -> `test_curation_rejects_duplicates`.
- Count/tokenizer/parity/checksum -> `test_curation_export_gate_failures`.
- Known checksum vector, order/unicode -> `test_curation_checksum_known_vector`.
- Defensive invalid configs -> `test_curation_config_failures`.
- Valid fixture passes -> `test_curation_valid_fixture_passes`.
- No toolkit import/network -> `test_curation_no_toolkit_or_network`.

## EVIDENCE

Save commands, exit codes, test IDs, and fixture results under `Project/reports/evidence/p6/`. Label CuratorKIT/AlignTune licence verification, real generation, and training `blocked` until explicitly run.

## STOP / BLOCKED

- Need to run CuratorKIT, install `curatorkit[all]`, add pdf/MinerU, or train: stop; later GPU/licence-gated stages.
- Test/OOD split or test-derived labels appear in any config/fixture: stop and report leakage immediately.
- A real tokenizer is required: use explicit observed counts only; do not invent tokenization.
- Any contract change needed: stop; orchestrator bumps v3.

CHANGES: v2 — aligned split vocabulary with P2; added complete-manifest/leakage gate, config/snapshot/task provenance, exact endpoint normalisation, five plan task configs, pinned checksum formula, tokenizer identity, and issue codes. Supersedes v1.
