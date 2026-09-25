from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.contracts import EmailRepository
from app.database import get_email_repository
from app.schemas import EmailResponse
from app.services import find_email, list_emails

router = APIRouter()


@router.get("/emails", response_model=list[EmailResponse])
def get_emails(
    repository: Annotated[EmailRepository, Depends(get_email_repository)],
    sender: str | None = None,
    subject: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    label: Annotated[str | None, Query(min_length=1)] = None,
) -> list[dict[str, Any]]:
    return list_emails(
        repository, sender=sender, subject=subject, limit=limit, offset=offset,
        date_from=date_from, date_to=date_to, label=label,
    )


@router.get("/emails/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: str,
    repository: Annotated[EmailRepository, Depends(get_email_repository)],
) -> dict[str, Any]:
    return find_email(email_id, repository)
