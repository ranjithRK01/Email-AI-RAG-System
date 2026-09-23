from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmailData:
    id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    body_text: str
    received_at: str
    labels: list[str]
    attachments: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailData":
        return cls(**data)
