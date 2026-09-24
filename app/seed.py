import argparse
from datetime import datetime
from getpass import getpass
import json
from typing import Any

from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Email
from app.repositories import DatabaseEmailRepository
from app.schemas import EmailResponse


def prepare_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty list of emails")
    prepared = []
    for record in records:
        values = EmailResponse.model_validate(record).model_dump()
        values["received_at"] = datetime.fromisoformat(values["received_at"])
        if values["received_at"].utcoffset() is None:
            raise ValueError("Email timestamp must include a timezone")
        prepared.append(values)
    if len({record["id"] for record in prepared}) != len(prepared):
        raise ValueError("Duplicate fixture IDs")
    return prepared


def seed_records(session: Session, records: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = existing = 0
    for values in records:
        stored = session.get(Email, values["id"])
        if stored is None:
            session.add(Email(**values))
            inserted += 1
        elif all(getattr(stored, field) == value for field, value in values.items()):
            existing += 1
        else:
            raise ValueError("Existing row conflicts with fixture; seed must roll back")
    return inserted, existing


def main() -> int:
    parser = argparse.ArgumentParser(description="Load synthetic emails into PostgreSQL.")
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
            print("DATABASE_URL is not set. Run python -m app.seed --prompt locally.")
            return 2

        with settings.email_data_path.open(encoding="utf-8") as data_file:
            records = prepare_records(json.load(data_file))
        engine = create_engine(url, connect_args={"connect_timeout": 5}, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        try:
            with SessionLocal.begin() as session:
                inserted, existing = seed_records(session, records)
            print(f"Committed: inserted={inserted}, already_present={existing}")
            with SessionLocal() as session:
                stored_records = DatabaseEmailRepository(session).list_all()
                stored_by_id = {record["id"]: record for record in stored_records}
                for values in records:
                    stored = stored_by_id.get(values["id"])
                    if stored is None:
                        raise ValueError("Committed fixture row missing")
                    actual = {**stored, "received_at": datetime.fromisoformat(stored["received_at"])}
                    if actual != values:
                        raise ValueError("Committed fixture row differs")
            print(f"PASS: verified {len(records)} fixture rows in a fresh session; database_total={len(stored_records)}.")
        finally:
            engine.dispose()
        print("Sessions closed and engine disposed.")
        return 0
    except (SQLAlchemyError, ValueError, OSError, KeyError, TypeError) as error:
        print(f"FAIL: seed or verification failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
