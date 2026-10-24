# P3 — ingestion, canonical source maps, and ACL-first retrieval contract v1

OWNER: orchestrator
OBJECTIVE: Turn lawful local files into deterministic, hash-verifiable chunks with provable text/page ranges, then retrieve only authorized active evidence into a frozen bundle plus trace before any model call.

IN SCOPE (batch 1, two disjoint writers):
- P3A: text/Markdown extraction, optional PDF extraction with an explicit unsupported state, canonical chunking, stable chunk IDs, extraction/source/page maps, unit tests.
- P3B: pure BM25 sparse retrieval over P2-authorized `EvidenceChunk` values, separate stale-candidate path, deterministic `EvidenceBundle`, retrieval trace, ACL/security tests.
- No registry mutation by P3A/P3B; integration into `CorpusRegistry.add_chunk` and `build_snapshot` is a batch-2 continuation owned by the orchestrator.

OUT OF SCOPE:
- SGLang, prompts, model calls, validation, repair, UI, curation, training, evaluation.
- Dense/FAISS retrieval, cross-encoder reranking, network services.
- Editing P1 or P2 frozen files. P3B must consume `CorpusRegistry.authorized_chunks`/`stale_chunks`; it must never query the corpus DB directly.

## FROZEN INTERFACES

### P3A — `hallx.ingestion`

Required Pydantic v2 frozen models (`extra="forbid"`):

```text
SourcePage(page_number:int >=1, text:str, extraction_char_start:int >=0, extraction_char_end:int > start)
ExtractionResult(source_sha256:hex64, media_type:str, extraction_text:str,
                 pages:tuple[SourcePage,...], unsupported_mapping:bool,
                 unsupported_reason:str|None)
ChunkDraft(chunk_id:str, chunk_index:int >=0,
           original_text:str, canonical_text:str,
           canonical_char_start:int >=0, canonical_char_end:int > start,
           original_char_start:int >=0, original_char_end:int > start,
           page_start:int|None, page_end:int|None,
           source_map_supported:bool, unsupported_reason:str|None)
IngestionResult(doc_id:str, version_id:str, source_sha256:hex64,
                canonicalization_version:str, extraction:ExtractionResult,
                chunks:tuple[ChunkDraft,...])
```

Required functions:

```text
extract_path(path: str|Path, *, media_type: str) -> ExtractionResult
chunk_extraction(extraction: ExtractionResult, *, doc_id: str, version_id: str,
                 max_chars: int = 1200, overlap_chars: int = 100) -> tuple[ChunkDraft,...]
ingest_path(path: str|Path, *, doc_id: str, version_id: str, media_type: str,
            max_chars: int = 1200, overlap_chars: int = 100) -> IngestionResult
```

Rules:
- `source_sha256` is SHA-256 of the exact source bytes. `IngestionResult.canonicalization_version` must equal `hallx.canonical.CANONICALIZATION_VERSION`.
- Extraction text is raw extracted text; `ChunkDraft.canonical_text` must already be canonical under `canonicalize()`. `canonical_char_start/end` index `canonicalize(extraction.extraction_text).text`; `original_char_start/end` index the extraction text.
- `chunk_id = "chk-" + sha256(f"{doc_id}\0{version_id}\0{chunk_index}\0{canonical_text}")` full 64 hex. Stable across runs and process restarts.
- Chunk ranges are half-open, disjoint per chunk except configured overlap; every canonical character is covered at most once in chunk order for non-overlapping boundaries. Never synthesize a page or source range.
- Text/Markdown is supported. PDF is supported only via an available verified extractor; if no page/coordinate mapping can be proven, return `unsupported_mapping=True`, `source_map_supported=False`, and a typed error during `ingest_path` (`SOURCE_MAP_UNSUPPORTED`). Do not return fake page numbers or highlights.
- `ChunkDraft.original_text` is the extraction-text slice corresponding to the canonical range; passing it to P2 `add_chunk` must reproduce the same canonical text.
- No ACL decisions, no corpus writes, no model calls.

### P3B — `hallx.retrieval`

Required models:

```text
ScoredChunk(chunk_id:str, score:float, rank:int >=0)
RetrievalTrace(trace_id:str, query_sha256:hex64, snapshot_id:str,
               as_of:date, index_version:str,
               candidate_count:int >=0, selected_chunk_ids:tuple[str,...],
               stale_chunk_ids:tuple[str,...], top_k:int >0,
               scores:tuple[ScoredChunk,...])
RetrievalResult(bundle:EvidenceBundle, trace:RetrievalTrace)
```

Required API:

```text
SparseIndex(chunks: Iterable[EvidenceChunk])
SparseIndex.search(query: str, *, top_k: int) -> tuple[ScoredChunk,...]
Retriever(registry: CorpusRegistry)
Retriever.retrieve(actor: Principal, query: str, *, as_of: date,
                   snapshot_id: str|None = None, top_k: int = 8,
                   conflict_pairs: tuple[ConflictPair,...] = (),
                   include_stale: bool = True) -> RetrievalResult
```

Rules:
- `Retriever.retrieve` calls `registry.authorized_chunks(actor, as_of=..., snapshot_id=...)` **before** building or searching any index. It must never read raw SQL, enumerate unauthorized IDs, or accept a client-provided chunk list.
- Ranking is deterministic BM25 over `EvidenceChunk.canonical_text`, casefolded with a fixed tokenizer; ties break by `chunk_id` ascending. `index_version` is `"bm25-v1"`. Empty/whitespace query fails with a typed `RETRIEVAL_QUERY_INVALID`; no result silently falls back to all chunks.
- `snapshot_id` is required (non-empty); `bundle.snapshot_id` must equal it. There is no empty-snapshot fallback.
- `bundle.chunks` contains only selected authorized active chunks.
- If `include_stale=True`, call `registry.stale_chunks` separately and place permitted stale chunks only in `bundle.stale_candidates`; never rank them into `bundle.chunks` or cite them as current support.
- `conflict_pairs` must reference selected chunks; reject otherwise with `RETRIEVAL_CONFLICT_INVALID`.
- `bundle_id = "bundle-" + sha256(snapshot_id + "\0" + query_sha256 + "\0" + "\0".join(sorted(selected_chunk_ids)))` full 64 hex.
- `trace_id = "trace-" + sha256(bundle_id + "\0" + index_version + "\0" + str(top_k))`; no wall-clock field in trace, so identical inputs produce identical outputs.
- `query_sha256 = sha256(canonical UTF-8 query)`; never log raw query text at INFO, never log restricted chunk text.
- No external calls, no SGLang, no network.

## WRITE PATHS

- P3A: `Project/src/hallx/ingestion/`, `Project/tests/unit/test_ingestion*.py`, `Project/tests/support_ingestion.py`, `Project/reports/evidence/p3/ingestion/`.
- P3B: `Project/src/hallx/retrieval/`, `Project/tests/unit/test_retrieval*.py`, `Project/tests/security/test_retrieval_acl.py`, `Project/reports/evidence/p3/retrieval/`.
- Orchestrator only: contracts, board, P2 integration, cross-phase reports, status file, commits.
- Neither worker edits `src/hallx/{models,canonical,source_map,errors}.py`, `src/hallx/validation/**`, `src/hallx/corpus/**`, specs, or the other worker’s paths.

## ACCEPTANCE

```powershell
uv run pytest tests/unit -q -k "ingestion or source_map"
uv run pytest tests/unit tests/security -q -k "retrieval"
uv run ruff check src/hallx/ingestion tests/unit/test_ingestion*.py tests/support_ingestion.py
uv run ruff check src/hallx/retrieval tests/unit/test_retrieval*.py tests/security/test_retrieval_acl.py
```

Pass criteria: commands exit 0; deterministic chunk IDs/ranges and bundle/trace; unsupported PDF mapping fails closed; no unauthorized chunk selected; stale candidates never in active bundle; no P1/P2 edits; no network.

## INVARIANTS / TESTS

- Stable source hash, canonical version, chunk IDs and ranges -> `test_ingestion_stable_ids_and_ranges`.
- Source map round-trip and unsupported mapping -> `test_ingestion_source_map_*`, `test_ingestion_unsupported_pdf_fails_closed`.
- ACL filtering before ranking -> `test_retrieval_acl_before_ranking`.
- Restricted/guessed chunk never selected -> `test_retrieval_restricted_chunk_not_selected`.
- Stale separated from active -> `test_retrieval_stale_is_diagnostic_only`.
- Deterministic bundle/trace -> `test_retrieval_bundle_reproducible`.
- Empty query and conflict-pair validation -> `test_retrieval_invalid_inputs_fail_closed`.
- No raw query/chunk text in logs or errors -> `test_retrieval_does_not_leak_text`.

## EVIDENCE

Save command, exit code, timestamp, worktree state, commit SHA, key output, test IDs under the phase evidence directories. No browser, API, GPU, or live-SGLang claim.

## STOP / BLOCKED

- PDF extractor/version unavailable: implement text/Markdown and return explicit unsupported PDF state; report partial, do not fake page maps.
- P2 API cannot express a required field without mutation: stop and report; no P1/P2 edit.
- A worker needs a contract change: stop, report, orchestrator bumps v2.

CHANGES: v1 initial (canonical 10-phase plan: P3 = ingestion/retrieval).
