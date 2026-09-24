from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_email_data_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMAIL_DATA_PATH", raising=False)
    expected = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    assert Settings().email_data_path == expected


def test_environment_overrides_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    alternate_file = tmp_path / "emails.json"
    alternate_file.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("EMAIL_DATA_PATH", str(alternate_file))
    assert Settings().email_data_path == alternate_file


def test_missing_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EMAIL_DATA_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(ValidationError) as error:
        Settings()
    assert error.value.errors()[0]["loc"] == ("email_data_path",)
    assert error.value.errors()[0]["type"] == "path_not_file"


def test_database_url_is_optional_for_json_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().database_url is None


def test_database_url_loads_and_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    synthetic_url = "postgresql://test_user:synthetic_password@127.0.0.1:5432/test_db"
    monkeypatch.setenv("DATABASE_URL", synthetic_url)
    settings = Settings()

    assert settings.database_url is not None
    assert settings.database_url.get_secret_value() == synthetic_url
    assert str(settings.database_url) == "**********"
    assert "synthetic_password" not in repr(settings)
    assert "synthetic_password" not in settings.model_dump_json()
