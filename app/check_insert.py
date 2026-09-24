import argparse
from datetime import datetime
from getpass import getpass
import json

from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Email


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert email_001 and verify it in a fresh session.")
    parser.add_argument("--prompt", action="store_true", help="Prompt for local credentials.")
    args = parser.parse_args()
    try:
        if args.prompt:
            host = input("Host [127.0.0.1]: ").strip() or "127.0.0.1"
            port = int(input("Port [5432]: ").strip() or "5432")
            database = input("Database [postgres]: ").strip() or "postgres"
            username = input("User [postgres]: ").strip() or "postgres"
            password = getpass("PostgreSQL password (hidden): ")
            url = URL.create(
                "postgresql+psycopg", username=username, password=password,
                host=host, port=port, database=database,
            )
        elif settings.database_url is not None:
            url = make_url(settings.database_url.get_secret_value())
            if url.drivername not in {"postgresql", "postgresql+psycopg"}:
                raise ValueError("Expected PostgreSQL using Psycopg")
            url = url.set(drivername="postgresql+psycopg")
        else:
            print("DATABASE_URL is not set. Run python -m app.check_insert --prompt locally.")
            return 2

        with settings.email_data_path.open(encoding="utf-8") as data_file:
            records = json.load(data_file)
        matches = [record for record in records if record["id"] == "email_001"]
        if len(matches) != 1:
            raise ValueError("Expected exactly one email_001 in the dataset")
        values = {**matches[0], "received_at": datetime.fromisoformat(matches[0]["received_at"])}
        engine = create_engine(url, connect_args={"connect_timeout": 5}, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        try:
            with SessionLocal() as session:
                if session.get(Email, "email_001") is not None:
                    print("STOP: email_001 already exists; no data changed.")
                    return 2
                session.add(Email(**values))
                session.commit()
            print("Committed: email_001")

            with SessionLocal() as session:
                stored_email = session.get(Email, "email_001")
                if stored_email is None or any(
                    getattr(stored_email, field) != value for field, value in values.items()
                ):
                    print("FAIL: committed row did not match all expected fields; inspect before retrying.")
                    return 1
            print("PASS: fresh session retrieved email_001; all 9 fields match.")
        finally:
            engine.dispose()
        print("Sessions closed and engine disposed.")
        return 0
    except (SQLAlchemyError, ValueError, OSError, KeyError, TypeError) as error:
        print(f"FAIL: insert/read check failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
