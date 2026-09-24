import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base, Email


def test_email_model_maps_synthetic_record_without_persisting() -> None:
    data_path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    record = json.loads(data_path.read_text(encoding="utf-8"))[0]
    email = Email(**{**record, "received_at": datetime.fromisoformat(record["received_at"])})

    assert email.id == "email_001"
    assert email.recipients == record["recipients"]
    assert email.received_at.tzinfo is not None
    assert inspect(email).transient
    assert Base.metadata.tables["emails"] is Email.__table__


def test_email_table_compiles_for_postgresql() -> None:
    sql = str(CreateTable(Email.__table__).compile(dialect=postgresql.dialect()))
    assert "PRIMARY KEY (id)" in sql
    assert "received_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "recipients JSON NOT NULL" in sql
