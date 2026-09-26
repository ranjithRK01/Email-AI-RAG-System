"""Verbose learning trace for the bundled synthetic fixtures only."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

from app.chunking import chunk_text
from app.cleaning import clean_email_text
from app.email_chunks import build_email_chunks
from email_data import EmailData


def inspect_email(email_id: str, max_chars: int) -> None:
    # Deliberately ignore configurable data paths: this command prints body text.
    path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    print("LEARNING TRACE: prints bundled synthetic email text; no database or AI calls.")
    with path.open(encoding="utf-8") as source:
        records = json.load(source)
    print(f"\n[1 PARSE JSON] file={path.name}; type=list; records={len(records)}")
    record = next((item for item in records if item["id"] == email_id), None)
    if record is None:
        raise ValueError("Email ID not found in synthetic fixtures")
    print("\n[2 SELECT RECORD] type=dict; fields=" + ", ".join(record))
    print(json.dumps(record, indent=2, ensure_ascii=False))

    email = EmailData.from_dict(record)
    print(f"\n[3 CREATE EmailData] type={type(email).__name__}; id={email.id}")
    print("This organizes fields; dataclass type hints are not runtime validation.")
    print(f"email.body_text={email.body_text!r}")

    cleaned = clean_email_text(email.body_text)
    print("\n[4 CLEAN BODY] remove_signature=False")
    print(f"before={email.body_text!r}")
    print(f"after ={cleaned!r}")
    print(f"characters: {len(email.body_text)} -> {len(cleaned)}; changed={cleaned != email.body_text}")

    pieces = chunk_text(cleaned, max_chars=max_chars)
    print(f"\n[5 SPLIT TEXT] max_chars={max_chars}; pieces={len(pieces)}; no overlap")
    for index, piece in enumerate(pieces):
        start = index * max_chars
        print(f"index={index}; slice=[{start}:{start + len(piece)}]; chars={len(piece)}; text={piece!r}")

    # Exercise the real builder too, rather than duplicating metadata assembly.
    chunks = build_email_chunks(email, max_chars=max_chars)
    print("\n[6 ATTACH METADATA] real build_email_chunks() output:")
    print("The builder repeats cleaning/splitting internally; the earlier stages are a preview.")
    for chunk in chunks:
        print(json.dumps(asdict(chunk), indent=2, ensure_ascii=False))
    assert [chunk.text for chunk in chunks] == pieces
    assert "".join(chunk.text for chunk in chunks) == cleaned
    assert email.body_text == record["body_text"]
    print("\n[7 VERIFY] PASS: chunks match preview; joined text equals cleaned body; original unchanged.")
    print("Returned objects are in memory only; no rows inserted and no embeddings generated.")


def inspect_edge_cases() -> None:
    """Trace intentionally invalid, synthetic inputs without printing private data."""
    sample = EmailData(
        id="demo", thread_id="demo_thread", sender="demo@example.com",
        recipients=[], subject="Synthetic edge case", body_text="Hello",
        received_at="2026-09-20T10:00:00Z", labels=[], attachments=[],
    )
    cases = [
        ("empty body", replace(sample, body_text=""), None),
        ("whitespace body", replace(sample, body_text=" \t\r\n "), None),
        ("null body", replace(sample, body_text=None), TypeError),
        ("numeric body", replace(sample, body_text=123), TypeError),
        ("blank email ID", replace(sample, id=" "), ValueError),
        ("labels supplied as a string", replace(sample, labels="job"), TypeError),
        ("dictionary instead of EmailData", {"body_text": "Hello"}, TypeError),
    ]
    print("EDGE-CASE TRACE: synthetic inputs only; no database writes or AI calls.")
    for name, value, expected_error in cases:
        print(f"\n[INPUT] {name}; object_type={type(value).__name__}")
        if isinstance(value, EmailData):
            print(f"body_type={type(value.body_text).__name__}; body={value.body_text!r}")
        print("[OPERATION] validate metadata -> clean body -> validate size/split -> attach metadata")
        try:
            chunks = build_email_chunks(value)
        except (TypeError, ValueError) as error:
            if expected_error is None or not isinstance(error, expected_error):
                raise
            print(f"[REJECTED] {type(error).__name__}: {error}")
            print("[RESULT] PASS: expected rejection; no chunk list returned.")
        else:
            assert expected_error is None
            assert chunks == []
            print(f"[CLEANED] {clean_email_text(value.body_text)!r}")
            print("[RESULT] PASS: 0 chunks; empty text is not sent for embedding.")
    print("\nPASS: all 7 edge cases behaved as expected.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email-id", default="email_001")
    parser.add_argument("--max-chars", type=int, default=60)
    parser.add_argument("--edge-cases", action="store_true", help="Explain empty and malformed synthetic inputs.")
    args = parser.parse_args()
    if args.max_chars <= 0:
        parser.error("--max-chars must be greater than zero")
    if args.edge_cases:
        inspect_edge_cases()
        return 0
    try:
        inspect_email(args.email_id, args.max_chars)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
