import json
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_email_repository, get_session_factory
from app.main import app
from app.models import Email
from app.repositories import DatabaseEmailRepository
from app.seed import prepare_records, seed_records


ROOT = Path(__file__).resolve().parents[1]


def test_live_schema_and_migration_revision(integration_engine: Engine) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    with integration_engine.connect() as connection:
        inspector = inspect(connection)
        columns = inspector.get_columns("emails")
        assert {column["name"] for column in columns} == set(Email.__table__.columns.keys())
        assert all(not column["nullable"] for column in columns)
        assert inspector.get_pk_constraint("emails")["constrained_columns"] == ["id"]
        assert set(MigrationContext.configure(connection).get_current_heads()) == set(ScriptDirectory.from_config(config).get_heads())


def test_live_repository_matches_fixture(integration_engine: Engine) -> None:
    expected = json.loads((ROOT / "test_data" / "emails.json").read_text(encoding="utf-8"))
    with Session(integration_engine) as session:
        repository = DatabaseEmailRepository(session)
        assert repository.list_all() == sorted(expected, key=lambda record: record["id"])
        assert repository.find_by_id("email_001") == expected[0]
        assert repository.find_by_id("missing") is None


def test_live_http_uses_postgresql(integration_engine: Engine) -> None:
    app.dependency_overrides.pop(get_email_repository)
    factory = sessionmaker(bind=integration_engine)
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as client:
        response = client.get("/emails", params={"sender": "RECRUITER", "subject": "PYTHON"})
        assert response.status_code == 200
        assert [record["id"] for record in response.json()] == ["email_001", "email_014"]
        assert client.get("/emails/email_001").status_code == 200
        missing = client.get("/emails/missing")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Email not found"}


def test_live_seed_has_no_new_work(integration_engine: Engine) -> None:
    records = prepare_records(json.loads((ROOT / "test_data" / "emails.json").read_text(encoding="utf-8")))
    with Session(integration_engine) as session:
        try:
            assert seed_records(session, records) == (0, 24)
        finally:
            session.rollback()
