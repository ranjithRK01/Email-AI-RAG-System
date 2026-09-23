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
        f"email_{number:03}" for number in range(1, 25)
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
