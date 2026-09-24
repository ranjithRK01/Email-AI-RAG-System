from sqlalchemy import Engine

from app.check_rollback import verify_rollback


def test_postgresql_transaction_rollback(integration_engine: Engine) -> None:
    verify_rollback(integration_engine)
