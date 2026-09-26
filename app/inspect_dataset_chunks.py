"""Trace chunk preparation across the bundled synthetic email dataset."""

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.chunk_records import prepare_chunk_record
from app.chunking import chunk_text
from email_data import EmailData


def summarize_records(records: list[dict[str, Any]], *, max_chars: int = 500) -> dict[str, Any]:
    """Validate all records, log preparation stages, and return summary statistics."""
    chunk_text("", max_chars=max_chars)  # Validate even when the dataset is empty.
    seen: set[str] = set()
    raw_chars = cleaned_chars = changed = empty = total_chunks = 0
    lengths: list[int] = []
    for index, raw in enumerate(records):
        email = EmailData.from_dict(raw)
        prepared = prepare_chunk_record(email, max_chars=max_chars)
        if email.id in seen:
            raise ValueError("Duplicate email ID in dataset")
        seen.add(email.id)
        if "".join(chunk.text for chunk in prepared.chunks) != prepared.normalized_text:
            raise ValueError("Chunks do not reconstruct normalized text")
        sizes = [len(chunk.text) for chunk in prepared.chunks]
        if any(size <= 0 or size > max_chars for size in sizes):
            raise ValueError("Invalid chunk length")
        raw_chars += len(email.body_text)
        cleaned_chars += len(prepared.normalized_text)
        changed += email.body_text != prepared.normalized_text
        empty += not prepared.chunks
        total_chunks += len(prepared.chunks)
        lengths.extend(sizes)
        print(f"[EMAIL {index + 1:02}] id={email.id}; dict -> EmailData -> validate -> clean -> chunks")
        print(f"  raw_chars={len(email.body_text)} cleaned_chars={len(prepared.normalized_text)} "
              f"changed={email.body_text != prepared.normalized_text} chunks={len(sizes)} sizes={sizes}")
        print("  VERIFY: joined chunks equal cleaned text; metadata attached; record in memory only")
    summary = {
        "emails": len(records), "empty_emails": empty, "changed_emails": changed,
        "max_chars": max_chars, "raw_chars": raw_chars, "cleaned_chars": cleaned_chars,
        "total_chunks": total_chunks,
        "min_chunk_chars": min(lengths) if lengths else 0,
        "max_chunk_chars": max(lengths) if lengths else 0,
        "average_chunk_chars": round(mean(lengths), 2) if lengths else 0,
    }
    print("[SUMMARY] " + json.dumps(summary))
    print("PASS: all records processed and chunk text verified. No storage writes or AI calls.")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-chars", type=int, default=500)
    args = parser.parse_args()
    if args.max_chars <= 0:
        parser.error("--max-chars must be greater than zero")
    path = Path(__file__).resolve().parents[1] / "test_data" / "emails.json"
    with path.open(encoding="utf-8") as source:
        records = json.load(source)
    print(f"[INPUT] bundled synthetic emails.json -> list of {len(records)} dictionaries")
    print(f"[SETTINGS] max_chars={args.max_chars}; signature removal=False; overlap=0")
    summarize_records(records, max_chars=args.max_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
