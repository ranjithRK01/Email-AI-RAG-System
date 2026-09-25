import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import URL

from app import concurrency_demo as demo


@pytest.mark.parametrize("requests,pool,delay", [(0, 3, 1), (1001, 3, 1), (10, 21, 1), (10, 3, 0), (1000, 1, 2)])
def test_demo_rejects_invalid_or_excessive_options(requests: int, pool: int, delay: float) -> None:
    with pytest.raises(ValueError):
        demo.validate_options(requests, pool, delay)


@pytest.mark.parametrize("failure_stage", [None, "acquire", "query"])
def test_demo_logs_queue_reuse_and_cleanup_with_simulated_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure_stage
) -> None:
    callbacks = {}
    state = {"borrowed": 0, "peak": 0, "created": 0, "disposed": False}
    idle = []
    semaphore = asyncio.Semaphore(2)

    def listener(target, name):
        def register(callback):
            callbacks[name] = callback
            return callback
        return register

    class FakeSession:
        record = None

        async def __aenter__(self):
            return self

        async def connection(self):
            if failure_stage == "acquire":
                raise RuntimeError("secret-password-and-host")
            await semaphore.acquire()
            if idle:
                self.record = idle.pop()
            else:
                self.record = SimpleNamespace(info={})
                state["created"] += 1
                callbacks["connect"](None, self.record)
            state["borrowed"] += 1
            state["peak"] = max(state["peak"], state["borrowed"])
            callbacks["checkout"](None, self.record, None)

        async def execute(self, statement, params):
            if failure_stage == "query":
                raise RuntimeError("secret-password-and-host")
            assert str(statement) == "SELECT pg_sleep(:delay)"
            assert params == {"delay": 0.1}
            await asyncio.sleep(0.01)
            return Mock()

        async def close(self):
            if self.record is not None:
                state["borrowed"] -= 1
                callbacks["checkin"](None, self.record)
                idle.append(self.record)
                semaphore.release()

    async def dispose():
        state["disposed"] = True

    engine = SimpleNamespace(
        sync_engine=object(), pool=SimpleNamespace(checkedout=lambda: state["borrowed"]), dispose=dispose
    )
    monkeypatch.setattr(demo.event, "listens_for", listener)
    monkeypatch.setattr(demo, "create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(demo, "async_sessionmaker", lambda **kwargs: FakeSession)
    if failure_stage is None:
        asyncio.run(demo.demonstrate(URL.create("postgresql+psycopg"), 6, 2, 0.1))
    else:
        with pytest.raises(ValueError, match="Some requests failed"):
            asyncio.run(demo.demonstrate(URL.create("postgresql+psycopg"), 6, 2, 0.1))
    output = capsys.readouterr().out
    assert "secret-password-and-host" not in output
    if failure_stage is not None:
        assert f"ERROR stage={failure_stage} type=RuntimeError" in output
        assert "successful=0/6, distinct_sessions=6, closed_sessions=6" in output
        assert state["borrowed"] == 0
        assert state["disposed"]
        return
    assert "successful=6/6, distinct_sessions=6, closed_sessions=6" in output
    assert "peak_borrowed=2, borrowed_now=0" in output
    assert "NEEDS CONNECTION" in output
    assert "ACQUIRED after" in output
    assert "CLIENT RECEIVED HTTP 200" in output
    assert state == {"borrowed": 0, "peak": 2, "created": 2, "disposed": True}


def test_safe_error_details_omits_sensitive_messages():
    from sqlalchemy.exc import OperationalError

    original = RuntimeError("secret-password")
    original.sqlstate = "28P01"
    error = OperationalError("private SQL", {"password": "secret"}, original)
    assert demo.safe_error_details(error) == (
        "type=OperationalError driver_type=RuntimeError sqlstate=28P01"
    )
    original.sqlstate = "secret-password"
    assert "sqlstate" not in demo.safe_error_details(error)
