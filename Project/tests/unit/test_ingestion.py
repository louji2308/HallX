from pathlib import Path

import pytest
from pydantic import ValidationError

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize
from hallx.errors import ErrorCode
from hallx.ingestion import (
    ChunkDraft,
    ExtractionResult,
    IngestionError,
    IngestionResult,
    SourcePage,
    chunk_extraction,
    extract_path,
    ingest_path,
)
from tests.support_corpus import (
    add_chunk as corpus_add_chunk,
)
from tests.support_corpus import (
    add_version,
    make_admin,
    register_document,
    registry_fixture,
)
from tests.support_ingestion import (
    expected_chunk_id,
    extraction_with_pages,
    sha256_bytes,
    write_bytes,
    write_text,
)

registry = registry_fixture


def test_ingestion_stable_ids_and_ranges(tmp_path: Path) -> None:
    raw = "Retention is 30 days.\n\nBackups expire after 90 days.\n"
    path = write_text(tmp_path, "policy.txt", raw)

    first = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=18,
        overlap_chars=4,
    )
    second = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=18,
        overlap_chars=4,
    )

    assert first == second
    assert first.source_sha256 == sha256_bytes(raw.encode("utf-8"))
    assert first.canonicalization_version == CANONICALIZATION_VERSION
    assert first.extraction.media_type == "text/plain"
    assert first.extraction.pages == ()
    assert len(first.chunks) > 1

    canonical = canonicalize(raw)
    previous = None
    for index, chunk in enumerate(first.chunks):
        assert chunk.chunk_index == index
        assert chunk.chunk_id == expected_chunk_id(
            "doc-1", "version-1", index, chunk.canonical_text
        )
        assert (
            canonical.text[chunk.canonical_char_start : chunk.canonical_char_end]
            == chunk.canonical_text
        )
        assert (
            first.extraction.extraction_text[
                chunk.original_char_start : chunk.original_char_end
            ]
            == chunk.original_text
        )
        assert canonicalize(chunk.original_text).text == chunk.canonical_text
        assert len(chunk.canonical_text) == chunk.canonical_char_end - chunk.canonical_char_start
        assert len(chunk.original_text) == chunk.original_char_end - chunk.original_char_start
        assert len(chunk.canonical_text) <= 18
        assert chunk.page_start is None
        assert chunk.page_end is None
        assert chunk.source_map_supported is True
        assert chunk.unsupported_reason is None
        if previous is not None:
            assert chunk.canonical_char_start <= previous.canonical_char_end
            assert previous.canonical_char_end - chunk.canonical_char_start <= 4
        previous = chunk

    assert first.chunks[0].canonical_char_start == 0
    assert first.chunks[-1].canonical_char_end == len(canonical.text)


@pytest.mark.parametrize("raw", ["", " \t\r\n  \n"])
def test_ingestion_empty_and_whitespace(
    tmp_path: Path, raw: str
) -> None:
    path = write_text(tmp_path, "empty.txt", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
    )

    assert result.extraction.extraction_text == raw
    assert result.extraction.pages == ()
    assert result.chunks == ()
    assert result.source_sha256 == sha256_bytes(raw.encode("utf-8"))


def test_ingestion_unicode_nfkc_whitespace_and_expansion(tmp_path: Path) -> None:
    raw = "Ａ\tcorp\n\n policy  ﬀ"
    path = write_text(tmp_path, "unicode.txt", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=5,
        overlap_chars=0,
    )
    canonical = canonicalize(raw)

    assert canonical.text == "A corp policy ff"
    assert "".join(chunk.canonical_text for chunk in result.chunks) == canonical.text
    assert all(len(chunk.canonical_text) <= 5 for chunk in result.chunks)

    expansion_start = canonical.text.index("ff")
    containing = [
        chunk
        for chunk in result.chunks
        if chunk.canonical_char_start <= expansion_start < chunk.canonical_char_end
    ]
    assert len(containing) == 1
    assert containing[0].canonical_char_end == expansion_start + 2


def test_ingestion_never_splits_nfkc_expansion(tmp_path: Path) -> None:
    path = write_text(tmp_path, "ligature.txt", "ﬀ")

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=1,
        overlap_chars=0,
    )

    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.canonical_text == "ff"
    assert chunk.original_text == "ﬀ"
    assert chunk.original_char_start == 0
    assert chunk.original_char_end == 1


def test_ingestion_chunk_boundaries(tmp_path: Path) -> None:
    raw = "0123456789" * 5
    path = write_text(tmp_path, "digits.txt", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=12,
        overlap_chars=3,
    )

    assert [chunk.canonical_char_start for chunk in result.chunks] == [
        0,
        9,
        18,
        27,
        36,
        45,
    ]
    assert [chunk.canonical_char_end for chunk in result.chunks] == [
        12,
        21,
        30,
        39,
        48,
        50,
    ]
    assert [len(chunk.canonical_text) for chunk in result.chunks] == [12, 12, 12, 12, 12, 5]
    for previous, current in zip(result.chunks, result.chunks[1:]):
        assert previous.canonical_char_end - current.canonical_char_start == 3

    whole = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=1000,
        overlap_chars=0,
    )
    assert len(whole.chunks) == 1
    assert whole.chunks[0].canonical_text == raw


def test_ingestion_overlap_is_bounded_and_keeps_progress(tmp_path: Path) -> None:
    raw = "0123456789" * 3
    path = write_text(tmp_path, "digits.txt", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=5,
        overlap_chars=100,
    )

    assert len(result.chunks) > 1
    assert result.chunks[0].canonical_char_start == 0
    assert result.chunks[-1].canonical_char_end == len(canonicalize(raw).text)
    for previous, current in zip(result.chunks, result.chunks[1:]):
        assert current.canonical_char_start > previous.canonical_char_start
        assert previous.canonical_char_end - current.canonical_char_start <= 4
        assert len(current.canonical_text) <= 5


def test_ingestion_source_map_roundtrip(tmp_path: Path) -> None:
    raw = "  Ａlpha\t\tbeta\n\nGamma ﬁle  "
    path = write_text(tmp_path, "spacing.txt", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=7,
        overlap_chars=2,
    )
    canonical = canonicalize(raw)

    assert result.chunks
    for chunk in result.chunks:
        assert canonicalize(chunk.original_text).text == chunk.canonical_text
        assert canonical.to_original_span(
            chunk.canonical_char_start, chunk.canonical_char_end
        ) == (chunk.original_char_start, chunk.original_char_end)
        assert canonical.original_span_to_canonical(
            chunk.original_char_start, chunk.original_char_end
        ) == (chunk.canonical_char_start, chunk.canonical_char_end)


def test_ingestion_page_mapping(tmp_path: Path) -> None:
    page_texts = (
        "Page one has alpha.\n",
        "Page two has beta.\n",
        "Page three has gamma.",
    )
    extraction = extraction_with_pages(page_texts)

    chunks = chunk_extraction(
        extraction,
        doc_id="doc-1",
        version_id="version-1",
        max_chars=25,
        overlap_chars=0,
    )

    assert chunks
    assert any(
        chunk.page_start == 1 and chunk.page_end == 2 for chunk in chunks
    )
    assert any(
        chunk.page_start == 2 and chunk.page_end == 3 for chunk in chunks
    )
    assert chunks[-1].page_start == 3
    assert chunks[-1].page_end == 3

    for chunk in chunks:
        overlapping = tuple(
            page
            for page in extraction.pages
            if page.extraction_char_start < chunk.original_char_end
            and page.extraction_char_end > chunk.original_char_start
        )
        assert overlapping
        assert chunk.page_start == min(page.page_number for page in overlapping)
        assert chunk.page_end == max(page.page_number for page in overlapping)


def test_ingestion_never_invents_pages(tmp_path: Path) -> None:
    path = write_text(tmp_path, "policy.txt", "Retention is 30 days.")

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
    )

    assert result.extraction.pages == ()
    assert len(result.chunks) == 1
    assert result.chunks[0].page_start is None
    assert result.chunks[0].page_end is None


def test_ingestion_unsupported_pdf_fails_closed(tmp_path: Path) -> None:
    payload = b"%PDF-1.7\nRESTRICTED-SENTINEL-DO-NOT-LEAK"
    path = write_bytes(tmp_path, "policy.pdf", payload)

    extraction = extract_path(path, media_type="application/pdf; version=1.7")

    assert extraction.source_sha256 == sha256_bytes(payload)
    assert extraction.media_type == "application/pdf"
    assert extraction.extraction_text == ""
    assert extraction.pages == ()
    assert extraction.unsupported_mapping is True
    assert extraction.unsupported_reason
    assert "RESTRICTED-SENTINEL" not in str(extraction.unsupported_reason)

    with pytest.raises(IngestionError) as raised:
        ingest_path(
            path,
            doc_id="doc-1",
            version_id="version-1",
            media_type="application/pdf",
        )
    assert raised.value.code is ErrorCode.SOURCE_MAP_UNSUPPORTED
    assert "RESTRICTED-SENTINEL" not in str(raised.value)

    with pytest.raises(IngestionError) as chunk_raised:
        chunk_extraction(
            extraction,
            doc_id="doc-1",
            version_id="version-1",
        )
    assert chunk_raised.value.code is ErrorCode.SOURCE_MAP_UNSUPPORTED


def test_ingestion_markdown_is_extracted_verbatim(tmp_path: Path) -> None:
    raw = "# Policy\n\n- Retention: 30 days\n- Backup: 90 days\n"
    path = write_text(tmp_path, "policy.md", raw)

    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/markdown; charset=utf-8",
        max_chars=30,
        overlap_chars=0,
    )

    assert result.extraction.extraction_text == raw
    assert result.extraction.media_type == "text/markdown"
    assert "".join(chunk.canonical_text for chunk in result.chunks) == canonicalize(raw).text


def test_ingestion_chunks_roundtrip_through_corpus_registry(
    tmp_path: Path, registry
) -> None:
    raw = "Retention is 30 days. Backups expire after 90 days."
    path = write_text(tmp_path, "policy.txt", raw)
    result = ingest_path(
        path,
        doc_id="doc-1",
        version_id="version-1",
        media_type="text/plain",
        max_chars=20,
        overlap_chars=0,
    )
    assert len(result.chunks) > 1

    admin = make_admin(registry)
    register_document(
        registry,
        admin,
        doc_id="doc-1",
        family_id="family-1",
        source_sha256=result.source_sha256,
    )
    add_version(
        registry,
        admin,
        doc_id="doc-1",
        version_id="version-1",
        text=canonicalize(raw).text,
    )

    records = []
    for chunk in result.chunks:
        record = corpus_add_chunk(
            registry,
            admin,
            chunk_id=chunk.chunk_id,
            doc_id="doc-1",
            version_id="version-1",
            chunk_index=chunk.chunk_index,
            text=chunk.original_text,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        )
        assert record.original_text == chunk.original_text
        assert record.canonical_text == chunk.canonical_text
        assert record.canonicalization_version == CANONICALIZATION_VERSION
        records.append(record)

    assert [record.chunk_id for record in records] == [
        chunk.chunk_id for chunk in result.chunks
    ]


def test_ingestion_missing_and_unreadable_sources_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(IngestionError) as missing:
        ingest_path(
            tmp_path / "missing.txt",
            doc_id="doc-1",
            version_id="version-1",
            media_type="text/plain",
        )
    assert missing.value.code is ErrorCode.SCHEMA_INVALID

    with pytest.raises(IngestionError) as directory:
        ingest_path(
            tmp_path,
            doc_id="doc-1",
            version_id="version-1",
            media_type="text/plain",
        )
    assert directory.value.code is ErrorCode.SCHEMA_INVALID

    path = write_bytes(tmp_path, "invalid.txt", b"\xff\xfeRESTRICTED-SENTINEL")
    with pytest.raises(IngestionError) as invalid_utf8:
        extract_path(path, media_type="text/plain")
    assert invalid_utf8.value.code is ErrorCode.SCHEMA_INVALID
    assert "RESTRICTED-SENTINEL" not in str(invalid_utf8.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"doc_id": "", "version_id": "version-1", "media_type": "text/plain"},
        {"doc_id": "doc-1", "version_id": " ", "media_type": "text/plain"},
        {"doc_id": "doc\x001", "version_id": "version-1", "media_type": "text/plain"},
        {"doc_id": "doc-1", "version_id": "version-1", "media_type": ""},
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "application/msword",
        },
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "text/plain",
            "max_chars": 0,
        },
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "text/plain",
            "max_chars": -1,
        },
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "text/plain",
            "overlap_chars": -1,
        },
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "text/plain",
            "max_chars": True,
        },
        {
            "doc_id": "doc-1",
            "version_id": "version-1",
            "media_type": "text/plain",
            "overlap_chars": False,
        },
    ],
)
def test_ingestion_invalid_arguments_fail_closed(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    path = write_text(tmp_path, "policy.txt", "Retention is 30 days.")

    with pytest.raises(IngestionError) as raised:
        ingest_path(path, **kwargs)

    assert raised.value.code is ErrorCode.SCHEMA_INVALID
    assert "Retention" not in str(raised.value)


def test_ingestion_rejects_non_path_and_non_extraction_inputs(tmp_path: Path) -> None:
    with pytest.raises(IngestionError) as bad_path:
        extract_path(123, media_type="text/plain")  # type: ignore[arg-type]
    assert bad_path.value.code is ErrorCode.SCHEMA_INVALID

    extraction = extraction_with_pages(("alpha",))
    with pytest.raises(IngestionError) as bad_extraction:
        chunk_extraction("not-an-extraction", doc_id="doc-1", version_id="version-1")  # type: ignore[arg-type]
    assert bad_extraction.value.code is ErrorCode.SCHEMA_INVALID

    with pytest.raises(IngestionError) as bad_identity:
        chunk_extraction(extraction, doc_id=" ", version_id="version-1")
    assert bad_identity.value.code is ErrorCode.SCHEMA_INVALID


def test_ingestion_models_reject_unproven_ranges() -> None:
    with pytest.raises(ValidationError):
        SourcePage(
            page_number=0,
            text="alpha",
            extraction_char_start=0,
            extraction_char_end=5,
        )
    with pytest.raises(ValidationError):
        SourcePage(
            page_number=1,
            text="alpha",
            extraction_char_start=0,
            extraction_char_end=4,
        )

    extraction = extraction_with_pages(("alpha",))
    with pytest.raises(ValidationError):
        ExtractionResult(
            source_sha256=extraction.source_sha256,
            media_type="text/plain",
            extraction_text="alpha",
            pages=(
                SourcePage(
                    page_number=1,
                    text="beta",
                    extraction_char_start=0,
                    extraction_char_end=4,
                ),
            ),
            unsupported_mapping=False,
            unsupported_reason=None,
        )

    base: dict[str, object] = {
        "chunk_id": expected_chunk_id("doc-1", "version-1", 0, "alpha"),
        "chunk_index": 0,
        "original_text": "alpha",
        "canonical_text": "alpha",
        "canonical_char_start": 0,
        "canonical_char_end": 5,
        "original_char_start": 0,
        "original_char_end": 5,
        "page_start": None,
        "page_end": None,
        "source_map_supported": True,
        "unsupported_reason": None,
    }
    assert ChunkDraft(**base)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        ChunkDraft(**{**base, "canonical_text": "alph"})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChunkDraft(**{**base, "original_text": "alph"})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChunkDraft(**{**base, "chunk_id": "chunk-1"})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChunkDraft(**{**base, "page_start": 1})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChunkDraft(
            **{**base, "source_map_supported": False, "unsupported_reason": None}  # type: ignore[arg-type]
        )

    unsupported = ChunkDraft(
        **{
            **base,
            "source_map_supported": False,
            "unsupported_reason": "mapping not available",
        }  # type: ignore[arg-type]
    )
    assert unsupported.source_map_supported is False

    unsupported_extraction = ExtractionResult(
        source_sha256=extraction.source_sha256,
        media_type="application/pdf",
        extraction_text="alpha",
        pages=(),
        unsupported_mapping=True,
        unsupported_reason="mapping not available",
    )
    with pytest.raises(ValidationError):
        IngestionResult(
            doc_id="doc-1",
            version_id="version-1",
            source_sha256=extraction.source_sha256,
            canonicalization_version=CANONICALIZATION_VERSION,
            extraction=unsupported_extraction,
            chunks=(ChunkDraft(**base),),  # type: ignore[arg-type]
        )
