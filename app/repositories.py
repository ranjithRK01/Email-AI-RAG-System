import json
from typing import Any

from app.config import settings


class JsonEmailRepository:
    def list_all(self) -> list[dict[str, Any]]:
        with settings.email_data_path.open(encoding="utf-8") as data_file:
            return json.load(data_file)

    def find_by_id(self, email_id: str) -> dict[str, Any] | None:
        for email in self.list_all():
            if email["id"] == email_id:
                return email

        return None
