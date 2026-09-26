import json
from dataclasses import replace

import pytest

from app.chunk_records import prepare_chunk_record
from email_data import EmailData


@pytest.fixture
def email() -> EmailData:
    return EmailData("e1", "t1", "demo@example.com", [], "Demo", "  ABCDEF  ",
                     "2026-09-20T00:00:00Z", ["test"], [])


def test_record_json_round_trip(email: EmailData) -> None:
    record = prepare_chunk_record(email, max_chars=4)
    data = json.loads(json.dumps(record.to_dict()))
    assert data["schema_version"] == 1
    assert data["email_id"] == "e1"
    assert data["normalized_text"] == "ABCDEF"
    assert data["max_chars"] == 4
    assert data["cleaner_version"] == "plain-text-v1"
    assert data["chunker_version"] == "character-slices-v1"
    assert data["remove_signature"] is False
    assert [chunk["text"] for chunk in data["chunks"]] == ["ABCD", "EF"]
    assert all(chunk["email_id"] == data["email_id"] for chunk in data["chunks"])
    assert email.body_text == "  ABCDEF  "
    assert prepare_chunk_record(email, max_chars=4) == record


def test_serialized_record_is_detached(email: EmailData) -> None:
    record = prepare_chunk_record(email)
    data = record.to_dict()
    data["chunks"][0]["labels"].append("changed")
    assert record.chunks[0].labels == ("test",)
    assert email.labels == ["test"]


def test_empty_email_still_has_a_storage_record(email: EmailData) -> None:
    data = prepare_chunk_record(replace(email, body_text=" \n")).to_dict()
    assert data["email_id"] == "e1"
    assert data["normalized_text"] == ""
    assert data["chunks"] == []


def test_invalid_input_is_not_serialized(email: EmailData) -> None:
    with pytest.raises(ValueError):
        prepare_chunk_record(email, max_chars=0)
