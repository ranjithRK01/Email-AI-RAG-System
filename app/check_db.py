import argparse
from getpass import getpass

import psycopg

from app.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PostgreSQL with SELECT 1.")
    parser.add_argument("--prompt", action="store_true", help="Prompt for local connection details.")
    args = parser.parse_args()

    connection_options: dict[str, str | int] = {"connect_timeout": 5}
    connection_string = ""
    if args.prompt:
        connection_options.update(
            host=input("Host [127.0.0.1]: ").strip() or "127.0.0.1",
            port=input("Port [5432]: ").strip() or "5432",
            dbname=input("Database [postgres]: ").strip() or "postgres",
            user=input("User [postgres]: ").strip() or "postgres",
            password=getpass("PostgreSQL password (hidden): "),
        )
    elif settings.database_url is not None:
        connection_string = settings.database_url.get_secret_value()
    else:
        print("DATABASE_URL is not set. Run python -m app.check_db --prompt locally.")
        return 2

    try:
        with psycopg.connect(connection_string, **connection_options) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result != (1,):
                    print("FAIL: SELECT 1 returned an unexpected result.")
                    return 1
        print("PASS: SELECT 1 returned 1; cursor and connection closed.")
        return 0
    except psycopg.Error as error:
        print(f"FAIL: database check failed ({type(error).__name__}); connection details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
