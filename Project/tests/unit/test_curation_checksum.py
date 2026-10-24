import hashlib
import json

from hallx.curation import CurationTask, TrainingRecord, export_sha256
from tests.support_curation import make_config, make_record, make_source

EXPORT_PREFIX = b"hallx.curation.export.v1\n"
KNOWN_DIGEST = "069db947e40397b6144cf0a6e30d7498608fff9b0f88a5b51c654626a44849eb"


def _digest_from_line(line: str) -> str:
    return hashlib.sha256(EXPORT_PREFIX + line.encode("utf-8") + b"\n").hexdigest()


def test_curation_checksum_known_vector() -> None:
    record = TrainingRecord(
        sample_id="sample-1",
        run_id="fixture-curation-qa-v1",
        snapshot_id="snap-fixture-train-v1",
        config_sha256="0" * 64,
        task=CurationTask.QA,
        source_id="src-train-1",
        chunk_id="chunk-train-1",
        prompt="What is the retention period?",
        completion="The retention period is 30 days.",
        quote="The retention period is 30 days.",
        quote_start=0,
        quote_end=32,
    )
    manual = {
        "sample_id": "sample-1",
        "run_id": "fixture-curation-qa-v1",
        "snapshot_id": "snap-fixture-train-v1",
        "config_sha256": "0" * 64,
        "task": "qa",
        "source_id": "src-train-1",
        "chunk_id": "chunk-train-1",
        "prompt": "What is the retention period?",
        "completion": "The retention period is 30 days.",
        "quote": "The retention period is 30 days.",
        "quote_start": 0,
        "quote_end": 32,
    }
    assert record.model_dump(mode="json") == manual

    line = json.dumps(
        manual,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert _digest_from_line(line) == KNOWN_DIGEST
    assert export_sha256((record,)) == KNOWN_DIGEST

    config = make_config()
    first = make_record(
        config,
        make_source(
            "src-unicode-a",
            family_id="family-unicode-a",
            canonical_text="Café policy applies.",
        ),
        sample_id="sample-b",
        prompt="Résumé policies?",
    )
    second = make_record(
        config,
        make_source(
            "src-unicode-b",
            family_id="family-unicode-b",
            canonical_text="Zürich office hours.",
        ),
        sample_id="sample-a",
        prompt="Büro hours?",
    )
    sorted_records = [second, first]
    manual_records = {
        record.sample_id: record.model_dump(mode="json")
        for record in sorted_records
    }
    unicode_lines = [
        json.dumps(
            manual_records[sample_id],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        for sample_id in sorted(manual_records)
    ]
    unicode_digest = _digest_from_line("\n".join(unicode_lines))
    assert export_sha256((first, second)) == unicode_digest

    escaped_lines = [
        json.dumps(
            manual_records[sample_id],
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        for sample_id in sorted(manual_records)
    ]
    assert export_sha256((first, second)) != _digest_from_line("\n".join(escaped_lines))

    assert export_sha256(()) == hashlib.sha256(EXPORT_PREFIX + b"\n").hexdigest()
