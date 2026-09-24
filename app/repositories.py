import json
from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Email


class JsonEmailRepository:
    def list_all(self) -> list[dict[str, Any]]:
        with settings.email_data_path.open(encoding="utf-8") as data_file:
            return json.load(data_file)

    def find_by_id(self, email_id: str) -> dict[str, Any] | None:
        for email in self.list_all():
            if email["id"] == email_id:
                return email

        return None


class DatabaseEmailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[dict[str, Any]]:
        emails = self.session.scalars(select(Email).order_by(Email.id)).all()
        return [self._to_record(email) for email in emails]

    def find_by_id(self, email_id: str) -> dict[str, Any] | None:
        email = self.session.get(Email, email_id)
        return self._to_record(email) if email is not None else None

    @staticmethod
    def _to_record(email: Email) -> dict[str, Any]:
        return {
            "id": email.id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "recipients": list(email.recipients),
            "subject": email.subject,
            "body_text": email.body_text,
            "received_at": email.received_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "labels": list(email.labels),
            "attachments": list(email.attachments),
        }
