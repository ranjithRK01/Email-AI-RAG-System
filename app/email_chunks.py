"""Attach source metadata to the plain-text chunking baseline."""

from dataclasses import dataclass

from app.chunking import chunk_text
from app.cleaning import clean_email_text
from email_data import EmailData


@dataclass(frozen=True)
class EmailChunk:
    chunk_id: str
    email_id: str
    chunk_index: int
    text: str
    thread_id: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    received_at: str
    labels: tuple[str, ...]
    attachments: tuple[str, ...]


def build_email_chunks(email: EmailData, *, max_chars: int = 500) -> list[EmailChunk]:
    """Clean, split, and attach metadata without modifying the source email.

    IDs identify positions within an email, not immutable content versions.
    If the body or chunk size changes, replace all stored chunks for that email.
    Persistence and versioning are deliberately outside this learning step.
    """
    if not isinstance(email, EmailData):
        raise TypeError("email must be an EmailData object")
    for name in ("id", "thread_id", "sender", "subject", "received_at"):
        value = getattr(email, name)
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
    if not email.id.strip():
        raise ValueError("id must not be blank")
    for name in ("recipients", "labels", "attachments"):
        value = getattr(email, name)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise TypeError(f"{name} must be a list of strings")
    cleaned = clean_email_text(email.body_text)
    return [
        EmailChunk(
            chunk_id=f"{email.id}:chunk:{index:04d}",
            email_id=email.id,
            chunk_index=index,
            text=piece,
            thread_id=email.thread_id,
            sender=email.sender,
            recipients=tuple(email.recipients),
            subject=email.subject,
            received_at=email.received_at,
            labels=tuple(email.labels),
            attachments=tuple(email.attachments),
        )
        for index, piece in enumerate(chunk_text(cleaned, max_chars=max_chars))
    ]
