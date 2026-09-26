from dataclasses import FrozenInstanceError, replace

import pytest

from app.email_chunks import build_email_chunks
from app.cleaning import clean_email_text
from email_data import EmailData


@pytest.fixture
def email() -> EmailData:
    return EmailData(
        id="email_test", thread_id="thread_test", sender="sender@example.com",
        recipients=["reader@example.com"], subject="Python role",
        body_text="  ABCDEFGHI  ", received_at="2026-09-20T10:30:00Z",
        labels=["job"], attachments=["role.pdf"],
    )


def test_ids_order_and_text(email: EmailData) -> None:
    chunks = build_email_chunks(email, max_chars=4)
    assert [chunk.chunk_id for chunk in chunks] == [
        "email_test:chunk:0000", "email_test:chunk:0001", "email_test:chunk:0002",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert [chunk.text for chunk in chunks] == ["ABCD", "EFGH", "I"]
    assert "".join(chunk.text for chunk in chunks) == "ABCDEFGHI"
    assert email.body_text == "  ABCDEFGHI  "
    assert build_email_chunks(email, max_chars=4) == chunks


def test_every_chunk_has_source_metadata(email: EmailData) -> None:
    for chunk in build_email_chunks(email, max_chars=4):
        assert chunk.email_id == email.id
        assert chunk.thread_id == email.thread_id
        assert chunk.sender == email.sender
        assert chunk.subject == email.subject
        assert chunk.received_at == email.received_at
        assert chunk.recipients == tuple(email.recipients)
        assert chunk.labels == tuple(email.labels)
        assert chunk.attachments == tuple(email.attachments)


def test_metadata_lists_are_snapshots(email: EmailData) -> None:
    chunk = build_email_chunks(email)[0]
    email.labels.append("changed")
    email.recipients.append("another@example.com")
    email.attachments.clear()
    assert chunk.labels == ("job",)
    assert chunk.recipients == ("reader@example.com",)
    assert chunk.attachments == ("role.pdf",)
    with pytest.raises(FrozenInstanceError):
        chunk.text = "changed"  # type: ignore[misc]


def test_different_emails_have_different_ids(email: EmailData) -> None:
    first = build_email_chunks(email)[0]
    second = build_email_chunks(replace(email, id="another_email"))[0]
    assert first.chunk_id != second.chunk_id


@pytest.mark.parametrize("body", ["Hi", "A" * 20])
def test_short_or_exact_boundary_email_is_one_complete_chunk(email: EmailData, body: str) -> None:
    source = replace(email, body_text=body)
    chunks = build_email_chunks(source, max_chars=20)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == body
    assert chunk.chunk_id == "email_test:chunk:0000"
    assert chunk.chunk_index == 0
    assert chunk.email_id == source.id
    assert chunk.subject == source.subject
    assert chunk.sender == source.sender
    assert chunk.labels == tuple(source.labels)


def test_short_email_keeps_paragraphs_and_trims_outer_whitespace(email: EmailData) -> None:
    source = replace(email, body_text="  Hello\r\n\r\nCall me.  ")
    chunks = build_email_chunks(source)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello\n\nCall me."
    assert source.body_text == "  Hello\r\n\r\nCall me.  "


@pytest.mark.parametrize("length", [5000, 5123])
def test_long_email_preserves_order_content_and_metadata(email: EmailData, length: int) -> None:
    # Nonuniform text makes reordered or missing chunks observable.
    pattern = "Python role — PostgreSQL, AWS.\nSalary: USD 100,000.\n"
    # Keep exact length and a non-whitespace ending.
    body = (pattern * (length // len(pattern) + 1))[:length - 1] + "!"
    source = replace(email, body_text=body)
    chunks = build_email_chunks(source, max_chars=500)
    cleaned = clean_email_text(body)
    expected_count = (len(cleaned) + 499) // 500

    assert len(chunks) == expected_count
    assert all(len(chunk.text) == 500 for chunk in chunks[:-1])
    assert len(chunks[-1].text) == len(cleaned) - 500 * (expected_count - 1)
    assert all(0 < len(chunk.text) <= 500 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == cleaned
    assert [chunk.chunk_index for chunk in chunks] == list(range(expected_count))
    assert [chunk.chunk_id for chunk in chunks] == [
        f"{source.id}:chunk:{index:04d}" for index in range(expected_count)
    ]
    assert len({chunk.chunk_id for chunk in chunks}) == expected_count
    for chunk in chunks:
        assert chunk.email_id == source.id
        assert chunk.thread_id == source.thread_id
        assert chunk.sender == source.sender
        assert chunk.subject == source.subject
        assert chunk.received_at == source.received_at
        assert chunk.labels == tuple(source.labels)
    assert source.body_text == body
    assert build_email_chunks(source, max_chars=500) == chunks


def test_long_email_is_cleaned_before_chunking(email: EmailData) -> None:
    body = "  " + ("Python role.  \r\n\r\n\r\n" * 100) + "End.  "
    source = replace(email, body_text=body)
    chunks = build_email_chunks(source, max_chars=100)
    assert len(chunks) > 1
    assert "".join(chunk.text for chunk in chunks) == clean_email_text(body)
    assert all(0 < len(chunk.text) <= 100 for chunk in chunks)
    assert source.body_text == body


@pytest.mark.parametrize("body", ["", " \t\r\n "])
def test_empty_body_produces_no_chunks(email: EmailData, body: str) -> None:
    assert build_email_chunks(replace(email, body_text=body)) == []


@pytest.mark.parametrize("changes,error", [
    ({"body_text": None}, TypeError), ({"body_text": 123}, TypeError),
    ({"id": " "}, ValueError), ({"id": None}, TypeError),
    ({"labels": "job"}, TypeError), ({"labels": [1]}, TypeError),
    ({"recipients": None}, TypeError), ({"attachments": [None]}, TypeError),
    ({"subject": 123}, TypeError),
])
def test_malformed_fields_rejected(email: EmailData, changes: dict, error: type[Exception]) -> None:
    with pytest.raises(error):
        build_email_chunks(replace(email, **changes))


def test_dictionary_is_not_an_email_object() -> None:
    with pytest.raises(TypeError, match="EmailData"):
        build_email_chunks({"body_text": "Hello"})  # type: ignore[arg-type]
