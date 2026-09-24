from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.repositories import DatabaseEmailRepository


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    url = make_url(settings.database_url.get_secret_value())
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Expected a PostgreSQL URL using Psycopg")
    engine = create_engine(
        url.set(drivername="postgresql+psycopg"),
        connect_args={"connect_timeout": 5},
        echo=False,
    )
    return sessionmaker(bind=engine)


def get_db(
    factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_email_repository(
    session: Annotated[Session, Depends(get_db)],
) -> DatabaseEmailRepository:
    return DatabaseEmailRepository(session)


def dispose_database() -> None:
    if get_session_factory.cache_info().currsize:
        factory = get_session_factory()
        factory.kw["bind"].dispose()
        get_session_factory.cache_clear()
