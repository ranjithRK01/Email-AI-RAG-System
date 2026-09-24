import argparse
from getpass import getpass

from pydantic import SecretStr
from sqlalchemy import URL
import uvicorn

from app.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the API with PostgreSQL configuration.")
    parser.add_argument("--prompt", action="store_true")
    parser.add_argument("--port", type=int, default=8003, help="HTTP server port (not PostgreSQL port).")
    args = parser.parse_args()
    if args.prompt:
        host = input("Database host [127.0.0.1]: ").strip() or "127.0.0.1"
        try:
            port = int(input("Database port [5432]: ").strip() or "5432")
        except ValueError:
            print("FAIL: database port must be an integer.")
            return 2
        database = input("Database [postgres]: ").strip() or "postgres"
        username = input("User [postgres]: ").strip() or "postgres"
        password = getpass("PostgreSQL password (hidden): ")
        url = URL.create("postgresql+psycopg", username=username, password=password,
                         host=host, port=port, database=database)
        settings.database_url = SecretStr(url.render_as_string(hide_password=False))
    if settings.database_url is None:
        print("DATABASE_URL is not set. Run python -m app.run_api --prompt locally.")
        return 2
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
