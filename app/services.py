from typing import Any

from app.exceptions import EmailNotFoundError
from app.repositories import JsonEmailRepository


repository = JsonEmailRepository()


def list_emails(
    sender: str | None = None,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    emails = repository.list_all()

    if sender is not None:
        emails = [email for email in emails if sender.casefold() in email["sender"].casefold()]
    if subject is not None:
        emails = [email for email in emails if subject.casefold() in email["subject"].casefold()]

    return emails


def find_email(email_id: str) -> dict[str, Any]:
    email = repository.find_by_id(email_id)
    if email is None:
        raise EmailNotFoundError("Email not found")
    return email
