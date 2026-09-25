import argparse
import asyncio
from getpass import getpass
import sys

from sqlalchemy import URL, make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def check_connection(url: URL) -> None:
    engine = create_async_engine(url, connect_args={"connect_timeout": 5}, echo=False)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            try:
                if result.scalar_one() != 1:
                    raise ValueError("Unexpected SELECT result")
            finally:
                result.close()
    finally:
        await engine.dispose()
    print("PASS: async SELECT 1 returned 1; connection released and engine disposed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PostgreSQL through SQLAlchemy async.")
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
            print("DATABASE_URL is not set. Run python -m app.check_async --prompt locally.")
            return 2

        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        asyncio.run(check_connection(url), loop_factory=loop_factory)
        return 0
    except (SQLAlchemyError, ValueError) as error:
        print(f"FAIL: async database check failed ({type(error).__name__}); details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
