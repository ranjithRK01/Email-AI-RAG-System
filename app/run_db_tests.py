import argparse
from getpass import getpass
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import URL


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all tests against the migrated, seeded local PostgreSQL database.")
    parser.add_argument("--prompt", action="store_true", help="Prompt for local test database credentials.")
    parser.add_argument("--repository-only", action="store_true", help="Run isolated repository tests; requires migrated schema but no seed data.")
    args = parser.parse_args()
    environment = os.environ.copy()
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
        environment["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
    if not environment.get("TEST_DATABASE_URL"):
        print("TEST_DATABASE_URL is not set. Run python -m app.run_db_tests --prompt locally.")
        return 2
    environment.pop("DATABASE_URL", None)
    root = Path(__file__).resolve().parents[1]
    target = "tests/test_repository_integration.py" if args.repository_only else "tests"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--tb=short"],
        cwd=root, env=environment, check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
