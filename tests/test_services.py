"""Service behavior with in-memory data: no HTTP client or database required."""

from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from app.exceptions import EmailNotFoundError, InvalidEmailQueryError
from app.services import find_email, list_emails


class FakeEmailRepository:
    """Satisfies EmailRepository's methods without inheriting from it."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.list_calls = 0
        self.lookup_ids: list[str] = []

    def list_all(self) -> list[dict[str, Any]]:
        self.list_calls += 1
        return self.records

    def find_by_id(self, email_id: str) -> dict[str, Any] | None:
        self.lookup_ids.append(email_id)
        return next((record for record in self.records if record["id"] == email_id), None)


@pytest.fixture
def repository() -> FakeEmailRepository:
    # Deliberately unordered; only fields used by these service functions are needed.
    return FakeEmailRepository([
        {"id": "c", "sender": "recruiter@example.com", "subject": "Python follow-up",
         "labels": ["job"], "received_at": "2026-09-22T10:00:00Z"},
        {"id": "a", "sender": "friend@example.com", "subject": "Dinner",
         "labels": ["personal"], "received_at": "2026-09-20T10:00:00Z"},
        {"id": "b", "sender": "recruiter@example.com", "subject": "Python opportunity",
         "labels": ["job", "inbox"], "received_at": "2026-09-21T10:00:00Z"},
    ])


def test_list_sorts_without_changing_repository_data(repository: FakeEmailRepository) -> None:
    before = deepcopy(repository.records)
    result = list_emails(repository)
    assert [record["id"] for record in result] == ["a", "b", "c"]
    assert repository.records == before
    assert repository.list_calls == 1
    assert repository.lookup_ids == []


def test_combined_filters_run_before_pagination(repository: FakeEmailRepository) -> None:
    result = list_emails(
        repository, sender="RECRUITER", subject="PYTHON", label="job",
        date_from=date(2026, 9, 21), date_to=date(2026, 9, 22), limit=1, offset=1,
    )
    assert [record["id"] for record in result] == ["c"]
    assert repository.list_calls == 1


@pytest.mark.parametrize("options", [{"sender": "missing"}, {"label": "jo"}, {"offset": 3}])
def test_no_matches_returns_empty_list(repository: FakeEmailRepository, options: dict) -> None:
    assert list_emails(repository, **options) == []


def test_empty_repository() -> None:
    assert list_emails(FakeEmailRepository([])) == []


def test_find_uses_id_lookup_not_list(repository: FakeEmailRepository) -> None:
    assert find_email("b", repository) == repository.records[2]
    assert repository.lookup_ids == ["b"]
    assert repository.list_calls == 0


def test_missing_email_raises_domain_error(repository: FakeEmailRepository) -> None:
    with pytest.raises(EmailNotFoundError, match="^Email not found$"):
        find_email("missing", repository)
    assert repository.lookup_ids == ["missing"]
    assert repository.list_calls == 0


def test_invalid_date_range_never_reads_repository(repository: FakeEmailRepository) -> None:
    with pytest.raises(InvalidEmailQueryError):
        list_emails(repository, date_from=date(2026, 9, 22), date_to=date(2026, 9, 20))
    assert repository.list_calls == 0
    assert repository.lookup_ids == []
