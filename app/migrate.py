import argparse
from getpass import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import URL, create_engine, inspect, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models import Email


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply migrations and verify the emails table.")
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
            print("DATABASE_URL is not set. Run python -m app.migrate --prompt locally.")
            return 2

        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        engine = create_engine(url, connect_args={"connect_timeout": 5}, echo=False)
        try:
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                inspector = inspect(connection)
                if not inspector.has_table("emails"):
                    raise ValueError("Emails table missing")
                columns = inspector.get_columns("emails")
                if {column["name"] for column in columns} != set(Email.__table__.columns.keys()):
                    raise ValueError("Unexpected email columns")
                if any(column["nullable"] for column in columns):
                    raise ValueError("Unexpected nullable column")
                if inspector.get_pk_constraint("emails")["constrained_columns"] != ["id"]:
                    raise ValueError("Unexpected primary key")
                current_heads = set(MigrationContext.configure(connection).get_current_heads())
                if current_heads != expected_heads:
                    raise ValueError("Migration revision mismatch")
            print("PASS: migration committed; emails has 9 required columns and primary key id.")
            print("Applied revision:", ", ".join(sorted(current_heads)))
        finally:
            engine.dispose()
        print("Connection released and engine disposed.")
        return 0
    except (SQLAlchemyError, CommandError, ValueError) as error:
        print(f"FAIL: migration or verification failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
