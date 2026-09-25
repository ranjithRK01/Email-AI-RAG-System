import argparse
import asyncio
from getpass import getpass
import sys
from typing import Annotated

from fastapi import Depends, FastAPI
import httpx
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.async_database import get_async_db, get_async_session_factory
from app.config import settings


async def check_concurrency(url: URL) -> None:
    engine = create_async_engine(url, connect_args={"connect_timeout": 5}, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    pool = engine.pool
    barrier = asyncio.Barrier(3)
    sessions: list[AsyncSession] = []
    observed_counts: list[int] = []
    diagnostic_app = FastAPI()
    diagnostic_app.dependency_overrides[get_async_session_factory] = lambda: factory

    @diagnostic_app.get("/probe")
    async def probe(
        session: Annotated[AsyncSession, Depends(get_async_db)],
        overlap: bool = True,
    ) -> dict[str, int]:
        sessions.append(session)
        result = await session.execute(text("SELECT pg_backend_pid()"))
        try:
            backend_pid = result.scalar_one()
        finally:
            result.close()
        observed_counts.append(pool.checkedout())
        if overlap:
            await barrier.wait()
        return {"backend_pid": backend_pid}

    try:
        transport = httpx.ASGITransport(app=diagnostic_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://diagnostic") as client:
            print(f"Before requests: in_use={pool.checkedout()}")
            async with asyncio.timeout(20):
                async with asyncio.TaskGroup() as group:
                    tasks = [group.create_task(client.get("/probe")) for _ in range(3)]
            responses = [task.result() for task in tasks]
            if any(response.status_code != 200 for response in responses):
                raise ValueError("Unexpected HTTP response")
            backend_pids = {response.json()["backend_pid"] for response in responses}
            if len({id(session) for session in sessions}) != 3 or len(backend_pids) != 3:
                raise ValueError("Concurrent requests did not have separate sessions/connections")
            if max(observed_counts) != 3 or pool.checkedout() != 0:
                raise ValueError("Unexpected pool checkout/cleanup counts")
            print("PASS: 3 overlapping requests, 3 distinct sessions, 3 physical connections.")
            print(f"Peak in_use={max(observed_counts)}; after requests in_use={pool.checkedout()}")
            response = await client.get("/probe", params={"overlap": "false"})
            if response.status_code != 200 or response.json()["backend_pid"] not in backend_pids:
                raise ValueError("Expected a reused pooled connection")
            if pool.checkedout() != 0:
                raise ValueError("Connection was not returned after final request")
            print("PASS: subsequent request reused a pooled connection; in_use=0.")
    finally:
        await engine.dispose()
    print("Engine disposed; no email data changed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe concurrent async request sessions and PostgreSQL connections.")
    parser.add_argument("--prompt", action="store_true")
    args = parser.parse_args()
    try:
        if args.prompt:
            host = input("Host [127.0.0.1]: ").strip() or "127.0.0.1"
            port = int(input("Port [5432]: ").strip() or "5432")
            database = input("Database [postgres]: ").strip() or "postgres"
            username = input("User [postgres]: ").strip() or "postgres"
            password = getpass("PostgreSQL password (hidden): ")
            url = URL.create("postgresql+psycopg", username=username, password=password,
                             host=host, port=port, database=database)
        elif settings.database_url is not None:
            url = make_url(settings.database_url.get_secret_value())
            if url.drivername not in {"postgresql", "postgresql+psycopg"}:
                raise ValueError("Expected PostgreSQL using Psycopg")
            url = url.set(drivername="postgresql+psycopg")
        else:
            print("DATABASE_URL is not set. Run python -m app.check_concurrency --prompt locally.")
            return 2
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        asyncio.run(check_concurrency(url), loop_factory=loop_factory)
        return 0
    except Exception as error:
        print(f"FAIL: concurrency diagnostic failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
