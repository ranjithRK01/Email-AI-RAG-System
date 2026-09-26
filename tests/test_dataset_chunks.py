import json
from pathlib import Path

import pytest

from app.inspect_dataset_chunks import summarize_records


def fixture_records() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    records = fixture_records()
    before = json.dumps(records)
    summary = summarize_records(records)
    assert summary["emails"] == 24
    assert summary["total_chunks"] == 24
    assert summary["empty_emails"] == 0
    assert summary["changed_emails"] == 0
    assert summary["raw_chars"] == sum(len(record["body_text"]) for record in records)
    assert summary["cleaned_chars"] == summary["raw_chars"]
    assert 0 < summary["min_chunk_chars"] <= summary["max_chunk_chars"] <= 500
    assert json.dumps(records) == before
    assert "[SUMMARY]" in capsys.readouterr().out


def test_smaller_chunks_increase_count_without_losing_text() -> None:
    records = fixture_records()
    summary = summarize_records(records, max_chars=60)
    assert summary["total_chunks"] == sum((len(record["body_text"]) + 59) // 60 for record in records)
    assert summary["total_chunks"] > 24
    assert summary["max_chunk_chars"] == 60


def test_empty_dataset() -> None:
    summary = summarize_records([])
    assert summary["emails"] == summary["total_chunks"] == summary["average_chunk_chars"] == 0


def test_duplicate_ids_rejected() -> None:
    record = fixture_records()[0]
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_records([record, record])
