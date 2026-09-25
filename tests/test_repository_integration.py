from collections.abc import Iterator
from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Email
from app.repositories import DatabaseEmailRepository
from app.services import list_emails


@pytest.fixture
def stored_emails(integration_engine: Engine) -> Iterator[tuple[Session, list[dict]]]:
    prefix = f"repository_test_{uuid4().hex}"
    records = [
        {
            "id": f"{prefix}_{number}", "thread_id": prefix,
            "sender": f"{prefix}@example.com", "recipients": ["candidate@example.com"],
            "subject": "Python role", "body_text": "Synthetic repository test.",
            "received_at": f"2026-09-{20 + number}T10:00:00Z",
            "labels": ["job", "test"], "attachments": ["description.pdf"],
        }
        for number in range(3)
    ]
    with Session(integration_engine) as session:
        try:
            for record in reversed(records):
                session.add(Email(**{
                    **record, "received_at": datetime.fromisoformat(record["received_at"]),
                }))
            session.flush()  # INSERT into PostgreSQL, without committing.
            session.expunge_all()  # Subsequent lookup must read from PostgreSQL.
            yield session, records
        finally:
            session.rollback()
    with Session(integration_engine) as verification:
        for record in records:
            assert verification.get(Email, record["id"]) is None


def test_repository_round_trip_and_order(stored_emails: tuple[Session, list[dict]]) -> None:
    session, records = stored_emails
    repository = DatabaseEmailRepository(session)
    assert repository.find_by_id(records[0]["id"]) == records[0]
    assert repository.find_by_id(f"{records[0]['id']}_missing") is None
    ids = {record["id"] for record in records}
    assert [record for record in repository.list_all() if record["id"] in ids] == records


def test_service_filters_and_paginates_real_repository(stored_emails: tuple[Session, list[dict]]) -> None:
    session, records = stored_emails
    repository = DatabaseEmailRepository(session)
    assert list_emails(
        repository, sender=records[0]["sender"].upper(), subject="PYTHON", label="job",
        date_from=date(2026, 9, 21), date_to=date(2026, 9, 22), limit=1, offset=1,
    ) == [records[2]]
    assert list_emails(repository, sender=records[0]["sender"], label="no-match") == []
