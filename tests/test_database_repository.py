from datetime import datetime
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app import services
from app.models import Email
from app.repositories import DatabaseEmailRepository


@pytest.fixture
def record() -> dict:
    path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    return json.loads(path.read_text(encoding="utf-8"))[0]


def test_database_record_matches_json_contract(record: dict) -> None:
    session = Mock(spec=Session)
    email = Email(**{**record, "received_at": datetime.fromisoformat(record["received_at"])})
    session.get.return_value = email
    result = DatabaseEmailRepository(session).find_by_id("email_001")
    assert result == record
    session.get.assert_called_once_with(Email, "email_001")
    result["labels"].append("temporary")
    assert email.labels == record["labels"]
    session.commit.assert_not_called()
    session.close.assert_not_called()


def test_missing_database_record_returns_none() -> None:
    session = Mock(spec=Session)
    session.get.return_value = None
    assert DatabaseEmailRepository(session).find_by_id("missing") is None


def test_list_normalizes_timezone_and_works_with_service(
    record: dict
) -> None:
    session = Mock(spec=Session)
    email = Email(**{**record, "received_at": datetime.fromisoformat("2026-09-20T16:00:00+05:30")})
    session.scalars.return_value.all.return_value = [email]
    repository = DatabaseEmailRepository(session)
    assert services.list_emails(repository, sender="RECRUITER", subject="PYTHON") == [record]
    assert services.list_emails(repository, subject="unrelated") == []


def test_empty_database_returns_empty_list() -> None:
    session = Mock(spec=Session)
    session.scalars.return_value.all.return_value = []
    assert DatabaseEmailRepository(session).list_all() == []
