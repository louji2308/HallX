# P3B retrieval — acceptance evidence

- Worker: `P3B-retrieval` (canonical phase P3, Batch 1)
- Contract: `Project/reports/contracts/P3-ingestion-retrieval.md` v1 (unchanged)
- Timestamp (UTC): `2026-10-24T16:29:42Z`
- Git root: `C:/Users/LOUJAN B/HallX`; baseline `HEAD` `a88e484489bbae989c59d28a4ac31baa079188ff`
- Worktree: no tracked modifications (`git diff --name-only` empty). All P3B files are new untracked paths under the assigned write scope; no commit was made.
- Environment: Windows host, Python `3.11.9`, pydantic `2.14.1`, pytest `8.4.2`, ruff `0.16.0`. No GPU, no SGLang, no network, no model call.

## Acceptance commands (exact)

1. `uv run pytest tests/unit tests/security -q -k "retrieval"`
   - exit `0`
   - key output: `29 passed, 162 deselected in 7.08s`
   - log: `pytest-retrieval.log`
2. `uv run ruff check src/hallx/retrieval tests/unit/test_retrieval.py tests/security/test_retrieval_acl.py`
   - exit `0`
   - key output: `All checks passed!`
   - log: `ruff-acceptance.log`

Supplemental (own files outside the exact acceptance path list):

3. `uv run ruff check src/hallx/retrieval tests/unit/test_retrieval.py tests/unit/test_retrieval_sparse.py tests/security/test_retrieval_acl.py`
   - exit `0`; `All checks passed!` — `ruff-all-own-files.log`
4. `uv run pytest -q`
   - exit `0`; `191 passed in 18.73s` — `pytest-full-suite.log`

## Invariant coverage

| Invariant | Test id |
|---|---|
| ACL filtering strictly before any index is built | `test_retrieval_acl_before_ranking` (event order `authorized_chunks` -> `index` -> `stale_chunks`) |
| Restricted chunk never indexed, never selected | `test_retrieval_restricted_text_never_enters_index`, `test_retrieval_restricted_chunk_not_selected` |
| ACL revocation rechecked on the next retrieval | `test_retrieval_acl_revocation_removes_chunks`, `test_retrieval_stale_path_respects_revocation` |
| Cross-tenant and forged-tenant denial | `test_retrieval_cross_tenant_is_denied`, `test_retrieval_rejects_forged_tenant_actor` |
| Stale is diagnostic only; never active support or scored | `test_retrieval_stale_is_diagnostic_only` |
| Snapshot is a closed candidate set | `test_retrieval_snapshot_filter_is_closed` |
| Deterministic bundle id and trace id for identical inputs | `test_retrieval_returns_authorized_active_chunks`, `test_retrieval_bundle_reproducible_across_registries` |
| Empty/tokenless query, invalid top_k, missing snapshot, bad as_of | `test_retrieval_invalid_inputs_fail_closed`, `test_empty_and_tokenless_queries_fail_closed` |
| Conflict pairs must reference selected chunks | `test_retrieval_conflict_pairs_must_reference_selected_chunks`, `test_retrieval_cannot_target_restricted_chunk_via_conflicts` |
| No raw query/chunk text in logs, errors, or trace | `test_retrieval_does_not_leak_text` |
| top_k and no-match behavior (no all-chunk fallback) | `test_retrieval_top_k_limits_selection`, `test_retrieval_no_match_returns_empty_bundle`, `test_top_k_truncates_after_deterministic_ranking` |
| BM25 determinism, tie-break by `chunk_id`, tokenizer | `test_bm25_ranks_and_breaks_ties_by_chunk_id`, `test_search_is_independent_of_construction_order`, `test_tokenizer_is_fixed_and_casefolded` |
| Model-level fail-closed bundle/trace consistency | `test_retrieval_result_models_fail_closed` |

## Contract interpretations and flags

1. `Retriever.retrieve` keeps the frozen signature `snapshot_id: str | None = None`, but the contract also says the snapshot is required and there is no empty-snapshot fallback. Implemented as: `None`/blank raises the local typed `RETRIEVAL_SNAPSHOT_INVALID`; `None` is never forwarded to the registry.
2. The contract names `RETRIEVAL_QUERY_INVALID` and `RETRIEVAL_CONFLICT_INVALID` as typed errors but does not place them in `hallx.errors.ErrorCode`, and P3B may not edit `hallx/errors.py`. They live in `hallx.retrieval.errors.RetrievalErrorCode`; supporting fail-closed codes are also local: `RETRIEVAL_SNAPSHOT_INVALID`, `RETRIEVAL_TOP_K_INVALID`, `RETRIEVAL_AS_OF_INVALID`, `RETRIEVAL_INDEX_INVALID`, `RETRIEVAL_TENANT_MISMATCH`.
3. `query_sha256 = sha256(canonical UTF-8 query)` is implemented with `hallx.canonical.canonicalize()` (NFKC + whitespace collapse) before UTF-8 hashing. Case is preserved in the hash, so `retention` and `RETENTION` share ranking tokens but not a bundle id. No wall-clock field exists anywhere in the trace.
4. `include_stale=True` returns every permitted stale chunk from `registry.stale_chunks` (registry order, sorted by `chunk_id`) in `bundle.stale_candidates`; they are never indexed, scored, or placed in `bundle.chunks`.
5. `RetrievalTrace`/`RetrievalResult` add structural validators (bundle/trace snapshot agreement, selected ids match bundle order, stale ids match stale candidates, active status/freshness vs `as_of`, contiguous ranks) as defense in depth; these do not change the frozen fields or ID formulas.

## Artifacts

See `artifact-hashes.txt` for SHA-256 of every new source and test file. Evidence logs are small text only; they contain no restricted document text, query text, secrets, or model output.

## Not claimed

No browser, API, GPU, live-SGLang, network, or model-call evidence exists for this slice. No commit or push was performed.
