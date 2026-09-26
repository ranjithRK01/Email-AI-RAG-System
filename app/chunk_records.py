"""Versioned storage representation; persistence is intentionally separate."""

from dataclasses import asdict, dataclass
from typing import Any

from app.cleaning import clean_email_text
from app.email_chunks import EmailChunk, build_email_chunks
from email_data import EmailData


@dataclass(frozen=True)
class EmailChunkRecord:
    schema_version: int
    email_id: str
    normalized_text: str
    max_chars: int
    cleaner_version: str
    chunker_version: str
    remove_signature: bool
    chunks: tuple[EmailChunk, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return detached JSON-compatible data, including arrays for tuples."""
        import json

        return json.loads(json.dumps(asdict(self), ensure_ascii=False))


def prepare_chunk_record(email: EmailData, *, max_chars: int = 500) -> EmailChunkRecord:
    """Prepare one replaceable record per email; do not write any storage."""
    chunks = build_email_chunks(email, max_chars=max_chars)
    return EmailChunkRecord(
        schema_version=1,
        email_id=email.id,
        normalized_text=clean_email_text(email.body_text),
        max_chars=max_chars,
        cleaner_version="plain-text-v1",
        chunker_version="character-slices-v1",
        remove_signature=False,
        chunks=tuple(chunks),
    )
