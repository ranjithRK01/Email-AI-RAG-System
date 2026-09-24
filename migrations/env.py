from alembic import context
from sqlalchemy import create_engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models import Base


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    if settings.database_url is None:
        raise RuntimeError("Set DATABASE_URL locally before running online migrations")
    url = make_url(settings.database_url.get_secret_value())
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Expected a PostgreSQL URL using Psycopg")
    engine = create_engine(
        url.set(drivername="postgresql+psycopg"),
        connect_args={"connect_timeout": 5},
        echo=False,
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError as error:
        raise RuntimeError(
            f"Migration database operation failed ({type(error).__name__}); details omitted"
        ) from None
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
