"""Explain the storage representation using one bundled synthetic email."""

import json
from pathlib import Path

from app.chunk_records import prepare_chunk_record
from email_data import EmailData


def main() -> None:
    source = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    with source.open(encoding="utf-8") as stream:
        emails = json.load(stream)
    email = EmailData.from_dict(emails[0])
    print(f"[1 INPUT] bundled synthetic JSON -> EmailData; email_id={email.id}")
    record = prepare_chunk_record(email, max_chars=60)
    print("[2 PREPARE] validate -> clean -> split -> attach metadata -> storage record")
    print(f"normalized_chars={len(record.normalized_text)}; chunks={len(record.chunks)}")
    print("[3 SERIALIZE] EmailChunkRecord -> dictionary -> JSON string")
    serialized = json.dumps(record.to_dict(), indent=2, ensure_ascii=False)
    print(serialized)
    restored = json.loads(serialized)
    print("[4 PARSE BACK] JSON string -> dictionary, not an EmailChunkRecord object")
    assert restored == record.to_dict()
    assert "".join(chunk["text"] for chunk in restored["chunks"]) == restored["normalized_text"]
    print("[5 VERIFY] PASS: JSON round-trip preserves fields; chunks reconstruct normalized text.")
    print("[STORAGE] No file or database write occurred. This defines the record format only.")


if __name__ == "__main__":
    main()
