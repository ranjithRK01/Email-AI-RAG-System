from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.async_database import get_async_db, get_async_session_factory


@pytest.mark.parametrize("failure", [None, "handled", "unhandled"])
def test_async_session_lifecycle_per_request(failure: str | None) -> None:
    sessions: list[AsyncSession] = []
    closed: list[AsyncSession] = []

    class RecordingAsyncSession(AsyncSession):
        async def close(self) -> None:
            await super().close()
            closed.append(self)

    factory = async_sessionmaker(class_=RecordingAsyncSession)
    test_app = FastAPI()
    test_app.dependency_overrides[get_async_session_factory] = lambda: factory

    @test_app.get("/probe")
    async def probe(
        db: Annotated[AsyncSession, Depends(get_async_db)],
        same_db: Annotated[AsyncSession, Depends(get_async_db)],
    ) -> dict[str, bool]:
        assert db is same_db
        assert all(db is not item for item in closed)
        sessions.append(db)
        if failure == "handled":
            raise HTTPException(status_code=409, detail="Test failure")
        if failure == "unhandled":
            raise RuntimeError("Test failure")
        return {"session_available": True}

    with TestClient(test_app, raise_server_exceptions=False) as client:
        for index in range(2):
            response = client.get("/probe")
            assert response.status_code == {None: 200, "handled": 409, "unhandled": 500}[failure]
            if failure is None:
                assert response.json() == {"session_available": True}
            assert len(closed) == index + 1
            assert closed[index] is sessions[index]

    assert sessions[0] is not sessions[1]
