from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_emails(client: TestClient) -> None:
    response = client.get("/emails")
    assert response.status_code == 200
    assert [email["id"] for email in response.json()] == [
        f"email_{number:03}" for number in range(1, 21)
    ]


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"sender": "RECRUITER"}, ["email_001", "email_014", "email_023"]),
        ({"subject": "PYTHON"}, ["email_001", "email_002", "email_007", "email_014"]),
        (
            {"sender": "recruiter@example.com", "subject": "Senior Python Developer Opportunity"},
            ["email_001", "email_014"],
        ),
        ({"subject": "no-such-subject"}, []),
    ],
)
def test_filter_emails(
    client: TestClient, params: dict[str, str], expected_ids: list[str]
) -> None:
    response = client.get("/emails", params=params)
    assert response.status_code == 200
    assert [email["id"] for email in response.json()] == expected_ids


def test_get_email(client: TestClient) -> None:
    response = client.get("/emails/email_001")
    assert response.status_code == 200
    email = response.json()
    assert email["id"] == "email_001"
    assert email["sender"] == "recruiter@example.com"
    assert email["subject"] == "Senior Python Developer Opportunity"


def test_missing_email(client: TestClient) -> None:
    response = client.get("/emails/email_missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Email not found"}


def test_unknown_route(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "params,expected_ids",
    [
        ({"limit": 5, "offset": 0}, [f"email_{n:03}" for n in range(1, 6)]),
        ({"limit": 5, "offset": 5}, [f"email_{n:03}" for n in range(6, 11)]),
        ({"limit": 20, "offset": 20}, [f"email_{n:03}" for n in range(21, 25)]),
        ({"limit": 5, "offset": 24}, []),
        ({"limit": 100}, [f"email_{n:03}" for n in range(1, 25)]),
        ({"sender": "RECRUITER", "limit": 1, "offset": 1}, ["email_014"]),
    ],
)
def test_email_pagination(client, params, expected_ids):
    response = client.get("/emails", params=params)
    assert response.status_code == 200
    assert [email["id"] for email in response.json()] == expected_ids


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101},
    {"offset": -1}, {"limit": "hello"}, {"offset": "1.5"},
])
def test_invalid_pagination(client, params):
    assert client.get("/emails", params=params).status_code == 422


def test_pagination_orders_records_before_slicing():
    from app.services import list_emails

    class UnorderedRepository:
        def list_all(self):
            return [{"id": "c"}, {"id": "a"}, {"id": "b"}]

    assert list_emails(UnorderedRepository(), limit=1, offset=1) == [{"id": "b"}]


@pytest.mark.parametrize("params,expected_ids", [
    ({"label": "interview"}, ["email_003", "email_004", "email_018", "email_024"]),
    ({"label": "inter"}, []),
    ({"label": "INTERVIEW"}, []),
    ({"label": "unknown"}, []),
    ({"date_from": "2026-09-23"}, ["email_014", "email_016", "email_018", "email_024"]),
    ({"date_to": "2026-09-15"}, ["email_013", "email_020"]),
    ({"date_from": "2026-09-20", "date_to": "2026-09-20"},
     ["email_001", "email_002", "email_011", "email_012", "email_022"]),
    ({"sender": "RECRUITER", "label": "job", "date_from": "2026-09-20",
      "date_to": "2026-09-22", "limit": 1, "offset": 1}, ["email_023"]),
    ({"date_from": "2030-01-01"}, []),
])
def test_date_and_label_filters(client: TestClient, params: dict, expected_ids: list[str]) -> None:
    response = client.get("/emails", params=params)
    assert response.status_code == 200
    assert [email["id"] for email in response.json()] == expected_ids


@pytest.mark.parametrize("params", [
    {"date_from": "not-a-date"}, {"date_to": "2026-02-30"},
    {"date_from": "2026-09-23", "date_to": "2026-09-20"}, {"label": ""},
])
def test_invalid_filters(client: TestClient, params: dict) -> None:
    assert client.get("/emails", params=params).status_code == 422


def test_date_filter_uses_utc_day() -> None:
    from datetime import date
    from app.services import list_emails

    class OffsetRepository:
        def list_all(self):
            return [
                {"id": "a", "received_at": "2026-09-21T00:30:00+05:30"},
                {"id": "b", "received_at": "2026-09-20T23:30:00-05:00"},
                {"id": "c", "received_at": "2026-09-20T00:00:00Z"},
                {"id": "d", "received_at": "2026-09-20T23:59:59.999999Z"},
            ]

    emails = list_emails(OffsetRepository(), date_from=date(2026, 9, 20), date_to=date(2026, 9, 20))
    assert [email["id"] for email in emails] == ["a", "c", "d"]


@pytest.mark.parametrize("params", [
    {"sender": " "}, {"subject": ""}, {"label": "\t"},
    {"date_from": "2026-09-23", "date_to": "2026-09-20"},
])
def test_controlled_query_error_response(client: TestClient, params: dict) -> None:
    response = client.get("/emails", params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid email search parameters"}


def test_query_error_handler_does_not_expose_exception_message(client: TestClient, monkeypatch) -> None:
    from app import emails
    from app.exceptions import InvalidEmailQueryError

    def fail(*args, **kwargs):
        raise InvalidEmailQueryError("private-connection-details")

    monkeypatch.setattr(emails, "list_emails", fail)
    response = client.get("/emails")
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid email search parameters"}
