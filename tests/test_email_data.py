import json
from pathlib import Path

from email_data import EmailData


def test_test_data_loads_successfully() -> None:
    data_path = Path(__file__).parents[1] / "test_data" / "emails.json"
    records = json.loads(data_path.read_text(encoding="utf-8"))

    emails = [EmailData.from_dict(record) for record in records]

    assert len(emails) == 24
    assert emails[0].id == "email_001"
