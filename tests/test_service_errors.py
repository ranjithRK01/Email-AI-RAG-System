import pytest
from datetime import date
from unittest.mock import Mock

from app.exceptions import EmailNotFoundError, InvalidEmailQueryError
from app.services import find_email, list_emails
from app.repositories import JsonEmailRepository


def test_missing_email_raises_application_error() -> None:
    with pytest.raises(EmailNotFoundError, match="^Email not found$"):
        find_email("email_missing", JsonEmailRepository())


@pytest.mark.parametrize("options", [
    {"limit": 0}, {"limit": 101}, {"offset": -1},
    {"date_from": date(2026, 9, 23), "date_to": date(2026, 9, 20)},
    {"sender": ""}, {"sender": "   "}, {"subject": "\t"}, {"label": " "},
])
def test_invalid_query_does_not_read_repository(options: dict) -> None:
    repository = Mock()
    with pytest.raises(InvalidEmailQueryError):
        list_emails(repository, **options)
    repository.list_all.assert_not_called()
