import argparse
import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from contextvars import ContextVar
from getpass import getpass
from math import ceil
from time import perf_counter
import sys
from typing import Annotated

from fastapi import Depends, FastAPI
import httpx
from sqlalchemy import URL, event, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def safe_error_details(error: Exception) -> str:
    """Report error categories, never exception messages, SQL, or credentials."""
    original = getattr(error, "orig", None)
    details = f"type={type(error).__name__}"
    if original is not None:
        details += f" driver_type={type(original).__name__}"
    state = getattr(original if original is not None else error, "sqlstate", None)
    if isinstance(state, str) and len(state) == 5 and all(
        char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for char in state
    ):
        details += f" sqlstate={state}"
    return details


def validate_options(requests: int, pool_size: int, delay: float) -> None:
    if not 1 <= requests <= 1000:
        raise ValueError("requests must be between 1 and 1000")
    if not 1 <= pool_size <= 20:
        raise ValueError("pool-size must be between 1 and 20")
    if not 0.1 <= delay <= 2:
        raise ValueError("delay must be between 0.1 and 2 seconds")
    if ceil(requests / pool_size) * delay > 120:
        raise ValueError("Use fewer requests, a shorter delay, or a larger pool: estimated query waves exceed 120 seconds")


async def demonstrate(url: URL, requests: int, pool_size: int, delay: float) -> None:
    validate_options(requests, pool_size, delay)
    started = perf_counter()
    request_context: ContextVar[int | None] = ContextVar("demo_request", default=None)
    active: set[int] = set()
    counts = {"connections": 0, "peak": 0, "waiting": 0, "closed": 0, "done": 0}
    acquisition_times: list[float] = []
    durations: list[float] = []
    sessions: list[AsyncSession] = []

    def log(message: str) -> None:
        request_id = request_context.get()
        label = f"R{request_id:04}" if request_id is not None else "SYSTEM"
        print(f"+{perf_counter() - started:7.3f}s {label:6} {message}", flush=True)

    engine = create_async_engine(
        url, pool_size=pool_size, max_overflow=0, pool_timeout=150,
        connect_args={"connect_timeout": 5}, echo=False,
    )
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    @event.listens_for(engine.sync_engine, "connect")
    def connected(dbapi_connection, connection_record) -> None:
        counts["connections"] += 1
        connection_record.info["demo_number"] = counts["connections"]

    @event.listens_for(engine.sync_engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy) -> None:
        number = connection_record.info["demo_number"]
        active.add(number)
        counts["peak"] = max(counts["peak"], len(active))
        log(f"CHECKOUT C{number:02} | borrowed={len(active)}/{pool_size}")

    @event.listens_for(engine.sync_engine, "checkin")
    def checkin(dbapi_connection, connection_record) -> None:
        number = connection_record.info["demo_number"]
        active.discard(number)
        log(f"RETURN   C{number:02} | borrowed={len(active)}/{pool_size}")

    app = FastAPI()

    async def get_demo_session(number: int) -> AsyncIterator[AsyncSession]:
        token = request_context.set(number)
        log("ARRIVED; creating a new session (no connection borrowed yet)")
        try:
            session = factory()
            sessions.append(session)
            try:
                yield session
            finally:
                try:
                    await session.close()
                except Exception as error:
                    log(f"ERROR stage=cleanup {safe_error_details(error)}")
                    raise
                counts["closed"] += 1
                log("SESSION CLOSED")
        finally:
            request_context.reset(token)

    @app.get("/probe/{number}")
    async def probe(number: int, session: Annotated[AsyncSession, Depends(get_demo_session)]) -> dict[str, int]:
        counts["waiting"] += 1
        log("NEEDS CONNECTION; awaiting pool checkout")
        waiting_since = perf_counter()
        try:
            await session.connection()
        except Exception as error:
            log(f"ERROR stage=acquire {safe_error_details(error)}")
            raise
        finally:
            counts["waiting"] -= 1
        waited = perf_counter() - waiting_since
        acquisition_times.append(waited)
        log(f"ACQUIRED after {waited:.3f}s (queue + connection setup); starting {delay:.1f}s DB query")
        try:
            result = await session.execute(text("SELECT pg_sleep(:delay)"), {"delay": delay})
            result.close()
        except Exception as error:
            log(f"ERROR stage=query {safe_error_details(error)}")
            raise
        log("QUERY FINISHED; connection stays borrowed until session cleanup")
        return {"request": number}

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(0.5)
            log(f"EVENT LOOP ALIVE | awaiting_connection={counts['waiting']} borrowed={len(active)} completed={counts['done']}/{requests}")

    async def send(client: httpx.AsyncClient, number: int) -> int:
        request_started = perf_counter()
        response = await client.get(f"/probe/{number}")
        duration = perf_counter() - request_started
        durations.append(duration)
        counts["done"] += 1
        token = request_context.set(number)
        try:
            log(f"CLIENT RECEIVED HTTP {response.status_code} | elapsed={duration:.3f}s")
        finally:
            request_context.reset(token)
        return response.status_code

    log(f"BEGIN: requests={requests}, connections_limit={pool_size}, query_delay={delay}s, overflow=0")
    log("HTTP runs in-process through FastAPI; database calls use real PostgreSQL.")
    pulse = asyncio.create_task(heartbeat())
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://demo",
        ) as client:
            async with asyncio.timeout(180):
                async with asyncio.TaskGroup() as group:
                    tasks = [group.create_task(send(client, number)) for number in range(1, requests + 1)]
        statuses = [task.result() for task in tasks]
        unique_sessions = len({id(session) for session in sessions})
        log(f"SUMMARY: successful={statuses.count(200)}/{requests}, distinct_sessions={unique_sessions}, closed_sessions={counts['closed']}")
        log(f"POOL: physical_connections_created={counts['connections']}, peak_borrowed={counts['peak']}, borrowed_now={len(active)}")
        if acquisition_times:
            log(f"ACQUIRE: min={min(acquisition_times):.3f}s max={max(acquisition_times):.3f}s")
        if durations:
            ordered = sorted(durations)
            log(f"REQUEST: min={ordered[0]:.3f}s max={ordered[-1]:.3f}s p95={ordered[ceil(len(ordered) * .95) - 1]:.3f}s")
        if statuses.count(200) != requests or unique_sessions != requests or counts["closed"] != requests:
            raise ValueError("Some requests failed or session lifecycle verification failed")
        if active or engine.pool.checkedout() != 0 or counts["peak"] > pool_size:
            raise ValueError("Pool bounds or connection cleanup verification failed")
        log("PASS: all requests succeeded; sessions isolated; connections returned.")
    finally:
        pulse.cancel()
        with suppress(asyncio.CancelledError):
            await pulse
        await engine.dispose()
        log("ENGINE DISPOSED; no email rows changed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Logged async concurrency learning demo (not a capacity benchmark).")
    parser.add_argument("--prompt", action="store_true")
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--pool-size", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0, help="Read-only PostgreSQL delay in seconds")
    args = parser.parse_args()
    try:
        validate_options(args.requests, args.pool_size, args.delay)
    except ValueError as error:
        parser.error(str(error))
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
            print("Run python -m app.concurrency_demo --prompt or configure DATABASE_URL.")
            return 2
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        asyncio.run(demonstrate(url, args.requests, args.pool_size, args.delay), loop_factory=loop_factory)
        return 0
    except Exception as error:
        print(f"FAIL: demonstration failed ({type(error).__name__}); connection details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
