import argparse
from getpass import getpass

from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings


def inspect_session(engine: Engine) -> None:
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        raise ValueError("Session inspection expects QueuePool")

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        print(f"Session created: in_transaction={session.in_transaction()}, in_use={pool.checkedout()}")
        if session.in_transaction() or pool.checkedout() != 0:
            raise ValueError("Expected a session with no connection checked out")
        with session.execute(text("SELECT 1")) as result:
            if result.scalar_one() != 1:
                raise ValueError("Unexpected SELECT result")
        print(f"After SELECT 1: in_transaction={session.in_transaction()}, in_use={pool.checkedout()}")
        if not session.in_transaction() or pool.checkedout() != 1:
            raise ValueError("Expected an active transaction and one checked-out connection")
    finally:
        session.close()
        print(f"After session.close(): in_transaction={session.in_transaction()}, in_use={pool.checkedout()}")

    if session.in_transaction() or pool.checkedout() != 0:
        raise ValueError("Session cleanup did not release its resources")
    print("PASS: session executed SELECT 1 and released its connection.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SELECT 1 through SQLAlchemy.")
    parser.add_argument("--prompt", action="store_true", help="Prompt for local connection details.")
    inspection = parser.add_mutually_exclusive_group()
    inspection.add_argument("--inspect-pool", action="store_true", help="Observe connection checkout, return, and reuse.")
    inspection.add_argument("--inspect-session", action="store_true", help="Create, use, and close one session.")
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
                print("FAIL: expected a PostgreSQL URL using Psycopg.")
                return 2
            url = url.set(drivername="postgresql+psycopg")
        else:
            print("DATABASE_URL is not set. Run python -m app.check_engine --prompt locally.")
            return 2

        engine = create_engine(url, connect_args={"connect_timeout": 5}, echo=False)
        print("Engine created; no database connection requested yet.")
        try:
            pool = engine.pool
            if args.inspect_session:
                inspect_session(engine)
                return 0
            if args.inspect_pool:
                if not isinstance(pool, QueuePool):
                    print("FAIL: pool inspection expects QueuePool.")
                    return 1
                print(f"Before checkout: idle={pool.checkedin()}, in_use={pool.checkedout()}")
            with engine.connect() as connection:
                if args.inspect_pool:
                    first_driver_connection = connection.connection.driver_connection
                    print(f"First checkout: idle={pool.checkedin()}, in_use={pool.checkedout()}")
                result = connection.execute(text("SELECT 1"))
                try:
                    if result.scalar_one() != 1:
                        print("FAIL: SELECT 1 returned an unexpected result.")
                        return 1
                finally:
                    result.close()
            if args.inspect_pool:
                print(f"After return: idle={pool.checkedin()}, in_use={pool.checkedout()}")
                with engine.connect() as second_connection:
                    reused = second_connection.connection.driver_connection is first_driver_connection
                    print(f"Second checkout: idle={pool.checkedin()}, in_use={pool.checkedout()}")
                    with second_connection.execute(text("SELECT 1")) as second_result:
                        if second_result.scalar_one() != 1 or not reused:
                            print("FAIL: expected a successful query on the reused connection.")
                            return 1
                    print("PASS: second checkout reused the same physical connection.")
                print(f"After second return: idle={pool.checkedin()}, in_use={pool.checkedout()}")
        finally:
            engine.dispose()
            if args.inspect_session:
                print("Engine disposed.")
            if args.inspect_pool:
                print(f"After dispose: idle={pool.checkedin()}, in_use={pool.checkedout()}")

        print("PASS: SELECT 1 returned 1; connection released and engine disposed.")
        return 0
    except (SQLAlchemyError, ValueError) as error:
        print(f"FAIL: engine check failed ({type(error).__name__}); connection details omitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
