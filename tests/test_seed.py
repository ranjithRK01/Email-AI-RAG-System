import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.models import Email
from app.seed import prepare_records, seed_records


@pytest.fixture
def records() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    return prepare_records(json.loads(path.read_text(encoding="utf-8")))


def test_seed_preserves_first_email_and_adds_missing_records(records: list[dict]) -> None:
    session = Mock(spec=Session)
    first = Email(**records[0])
    session.get.side_effect = lambda model, key: first if key == first.id else None
    assert seed_records(session, records) == (23, 1)
    assert [call.args[0].id for call in session.add.call_args_list] == [r["id"] for r in records[1:]]
    session.commit.assert_not_called()
    session.close.assert_not_called()


def test_conflicting_row_is_rejected(records: list[dict]) -> None:
    session = Mock(spec=Session)
    session.get.return_value = Email(**{**records[0], "subject": "Different"})
    with pytest.raises(ValueError, match="conflicts"):
        seed_records(session, records)
    session.add.assert_not_called()


def test_duplicate_fixture_ids_are_rejected(records: list[dict]) -> None:
    record = {**records[0], "received_at": records[0]["received_at"].isoformat()}
    with pytest.raises(ValueError, match="Duplicate"):
        prepare_records([record, record])


def test_repeated_seed_preserves_all_existing_records(records: list[dict]) -> None:
    stored = {record["id"]: Email(**record) for record in records}
    session = Mock(spec=Session)
    session.get.side_effect = lambda model, key: stored.get(key)

    for _ in range(2):
        assert seed_records(session, records) == (0, 24)

    session.add.assert_not_called()
    assert len(stored) == 24
    for record in records:
        assert all(getattr(stored[record["id"]], field) == value for field, value in record.items())
