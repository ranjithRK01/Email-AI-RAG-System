from collections.abc import Iterator
import os

import pytest
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import get_email_repository
from app.main import app
from app.repositories import JsonEmailRepository


@pytest.fixture(autouse=True)
def use_synthetic_repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "database_url", None)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_email_repository] = JsonEmailRepository
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def integration_engine() -> Iterator[Engine]:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Requires explicit TEST_DATABASE_URL")
    try:
        url = make_url(raw_url)
        if url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("Expected PostgreSQL")
        engine = create_engine(url.set(drivername="postgresql+psycopg"), connect_args={"connect_timeout": 5})
    except (SQLAlchemyError, ValueError):
        pytest.fail("Invalid test database configuration; details omitted", pytrace=False)
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            pytest.fail("Test database connection failed; details omitted", pytrace=False)
        yield engine
    finally:
        engine.dispose()
