from pathlib import Path

from pydantic import FilePath
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    email_data_path: FilePath = (
        Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    )


settings = Settings()
