import argparse
from datetime import datetime, timezone
from getpass import getpass
from uuid import uuid4

from sqlalchemy import URL, Engine, create_engine, make_url, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Email


class DeliberateRollback(Exception):
    """An intentional failure before commit."""


def verify_rollback(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine)
    probe_id = f"rollback_probe_{uuid4().hex}"
    try:
        with SessionLocal.begin() as session:
            session.add(Email(
                id=probe_id, thread_id=probe_id, sender="rollback@example.com",
                recipients=["candidate@example.com"], subject="Synthetic rollback check",
                body_text="Temporary transaction test.",
                received_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                labels=["test"], attachments=[],
            ))
            session.flush()
            with session.execute(select(Email.id).where(Email.id == probe_id)) as result:
                if result.scalar_one() != probe_id:
                    raise ValueError("Probe was not visible inside its transaction")
            print("Confirmed: INSERT was flushed and visible inside the transaction.")
            raise DeliberateRollback()
    except DeliberateRollback:
        print("Intentional failure: transaction context rolled back.")

    with SessionLocal() as session:
        if session.get(Email, probe_id) is not None:
            raise ValueError("Rollback failed: probe remains in database")
    print("PASS: fresh session found no probe row after rollback.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PostgreSQL transaction rollback.")
    parser.add_argument("--prompt", action="store_true", help="Prompt for local credentials.")
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
            print("DATABASE_URL is not set. Run python -m app.check_rollback --prompt locally.")
            return 2
        engine = create_engine(url, connect_args={"connect_timeout": 5}, echo=False)
        try:
            verify_rollback(engine)
        finally:
            engine.dispose()
        print("Sessions closed and engine disposed.")
        return 0
    except (SQLAlchemyError, ValueError) as error:
        print(f"FAIL: rollback check failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
