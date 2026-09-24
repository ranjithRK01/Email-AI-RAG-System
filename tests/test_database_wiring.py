from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_email_repository, get_session_factory
from app.main import app
from app.models import Email


def test_routes_use_database_repository_and_close_sessions() -> None:
    app.dependency_overrides.pop(get_email_repository)
    sessions: list[Mock] = []
    email = Email(id="db_only", thread_id="db_thread", sender="db@example.com",
                  recipients=[], subject="Database-only record", body_text="Synthetic",
                  received_at=datetime(2026, 9, 20, tzinfo=timezone.utc), labels=[], attachments=[])

    def factory() -> Mock:
        session = Mock(spec=Session)
        session.scalars.return_value.all.return_value = [email]
        session.get.side_effect = lambda model, key: email if key == "db_only" else None
        sessions.append(session)
        return session

    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        response = client.get("/emails")
        assert response.status_code == 200
        assert [record["id"] for record in response.json()] == ["db_only"]
        assert client.get("/emails/db_only").json()["id"] == "db_only"
        assert client.get("/emails/email_001").status_code == 404
    assert len(sessions) == 3
    for session in sessions:
        session.close.assert_called_once()
