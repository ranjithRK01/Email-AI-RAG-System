import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.request_logging import RequestLogFormatter


@pytest.mark.parametrize("path, status", [("/health", 200), ("/emails/missing", 404)])
def test_response_and_log_share_request_id(
    path: str, status: int, caplog: pytest.LogCaptureFixture
) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == status
    request_id = response.headers["X-Request-ID"]
    assert str(UUID(request_id)) == request_id
    records = [r for r in caplog.records if r.name == "email_platform.requests"]
    assert len(records) == 1
    entry = json.loads(RequestLogFormatter().format(records[0]))
    assert entry["request_id"] == request_id
    assert entry["status_code"] == status
    assert entry["duration_ms"] >= 0


def test_supplied_uuid_is_reused() -> None:
    request_id = "12345678-1234-4234-8234-123456789abc"
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": request_id})
    assert response.headers["X-Request-ID"] == request_id


def test_invalid_id_is_replaced_and_generated_ids_are_distinct() -> None:
    with TestClient(app) as client:
        first = client.get("/health", headers={"X-Request-ID": "invalid"})
        second = client.get("/health")
    assert str(UUID(first.headers["X-Request-ID"])) == first.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_request_log_excludes_query_and_email_content(caplog: pytest.LogCaptureFixture) -> None:
    with TestClient(app) as client:
        client.get("/emails", params={"sender": "recruiter@example.com"})
    record = next(r for r in caplog.records if r.name == "email_platform.requests")
    entry = json.loads(RequestLogFormatter().format(record))
    assert set(entry) == {
        "timestamp", "level", "event", "request_id", "method", "status_code", "duration_ms"
    }
    assert "recruiter@example.com" not in json.dumps(entry)
