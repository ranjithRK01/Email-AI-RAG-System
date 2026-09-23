from typing import Any

from fastapi import APIRouter

from app.schemas import EmailResponse
from app.services import find_email, list_emails

router = APIRouter()


@router.get("/emails", response_model=list[EmailResponse])
def get_emails(
    sender: str | None = None,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    return list_emails(sender=sender, subject=subject)


@router.get("/emails/{email_id}", response_model=EmailResponse)
def get_email(email_id: str) -> dict[str, Any]:
    return find_email(email_id)
