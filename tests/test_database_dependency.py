from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, get_session_factory


@pytest.mark.parametrize("failure", [None, "handled", "unhandled"])
def test_session_lifecycle_per_request(failure: str | None) -> None:
    sessions: list[Session] = []
    closed: list[Session] = []

    class RecordingSession(Session):
        def close(self) -> None:
            super().close()
            closed.append(self)

    factory = sessionmaker(class_=RecordingSession)
    test_app = FastAPI()
    test_app.dependency_overrides[get_session_factory] = lambda: factory

    @test_app.get("/probe")
    def probe(
        db: Annotated[Session, Depends(get_db)],
        same_db: Annotated[Session, Depends(get_db)],
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
