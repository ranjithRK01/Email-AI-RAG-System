from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    url = make_url(settings.database_url.get_secret_value())
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Expected PostgreSQL using Psycopg")
    engine = create_async_engine(
        url.set(drivername="postgresql+psycopg"),
        connect_args={"connect_timeout": 5},
        echo=False,
    )
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_async_db(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_async_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


async def dispose_async_database() -> None:
    if get_async_session_factory.cache_info().currsize:
        factory = get_async_session_factory()
        try:
            await factory.kw["bind"].dispose()
        finally:
            get_async_session_factory.cache_clear()
