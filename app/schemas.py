from pydantic import BaseModel


class EmailResponse(BaseModel):
    id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    body_text: str
    received_at: str
    labels: list[str]
    attachments: list[str]
