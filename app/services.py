from datetime import date, datetime, timezone
from typing import Any

from app.contracts import EmailRepository
from app.exceptions import EmailNotFoundError, InvalidEmailQueryError


def list_emails(
    repository: EmailRepository,
    sender: str | None = None,
    subject: str | None = None,
    limit: int = 20,
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    label: str | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100 or offset < 0:
        raise InvalidEmailQueryError("limit must be 1–100 and offset must be non-negative")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidEmailQueryError("date_from must be on or before date_to")
    for name, value in (("sender", sender), ("subject", subject), ("label", label)):
        if value is not None and not value.strip():
            raise InvalidEmailQueryError(f"{name} must not be blank")
    emails = repository.list_all()

    if sender is not None:
        emails = [email for email in emails if sender.casefold() in email["sender"].casefold()]
    if subject is not None:
        emails = [email for email in emails if subject.casefold() in email["subject"].casefold()]
    if label is not None:
        emails = [email for email in emails if label in email["labels"]]
    if date_from is not None or date_to is not None:
        matching = []
        for email in emails:
            received_at = datetime.fromisoformat(email["received_at"].replace("Z", "+00:00"))
            if received_at.tzinfo is None:
                raise ValueError("Email received_at must include a timezone")
            received_date = received_at.astimezone(timezone.utc).date()
            if date_from is not None and received_date < date_from:
                continue
            if date_to is not None and received_date > date_to:
                continue
            matching.append(email)
        emails = matching

    emails = sorted(emails, key=lambda email: email["id"])
    return emails[offset : offset + limit]


def find_email(email_id: str, repository: EmailRepository) -> dict[str, Any]:
    email = repository.find_by_id(email_id)
    if email is None:
        raise EmailNotFoundError("Email not found")
    return email
