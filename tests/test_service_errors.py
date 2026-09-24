import pytest

from app.exceptions import EmailNotFoundError
from app.services import find_email
from app.repositories import JsonEmailRepository


def test_missing_email_raises_application_error() -> None:
    with pytest.raises(EmailNotFoundError, match="^Email not found$"):
        find_email("email_missing", JsonEmailRepository())
