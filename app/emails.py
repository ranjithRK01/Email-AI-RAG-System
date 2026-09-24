from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.database import get_email_repository
from app.repositories import DatabaseEmailRepository
from app.schemas import EmailResponse
from app.services import find_email, list_emails

router = APIRouter()


@router.get("/emails", response_model=list[EmailResponse])
def get_emails(
    repository: Annotated[DatabaseEmailRepository, Depends(get_email_repository)],
    sender: str | None = None,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    return list_emails(repository, sender=sender, subject=subject)


@router.get("/emails/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: str,
    repository: Annotated[DatabaseEmailRepository, Depends(get_email_repository)],
) -> dict[str, Any]:
    return find_email(email_id, repository)
