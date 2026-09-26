import pytest

from app.chunking import chunk_text
from app.cleaning import clean_email_text


def test_splits_into_consecutive_chunks() -> None:
    assert chunk_text("ABCDEFGHIJK", max_chars=4) == ["ABCD", "EFGH", "IJK"]


def test_exact_multiple_has_no_empty_final_chunk() -> None:
    assert chunk_text("ABCDEFGH", max_chars=4) == ["ABCD", "EFGH"]


def test_preserves_whitespace_and_unicode() -> None:
    text = "Hello\n\nPython — नमस्ते 🙂\tend "
    chunks = chunk_text(text, max_chars=7)
    assert "".join(chunks) == text
    assert all(0 < len(chunk) <= 7 for chunk in chunks)
    assert chunk_text(text, max_chars=7) == chunks


def test_clean_then_chunk() -> None:
    cleaned = clean_email_text("  Python\r\n\r\nRole  ")
    chunks = chunk_text(cleaned, max_chars=6)
    assert chunks == ["Python", "\n\nRole"]
    assert "".join(chunks) == cleaned


@pytest.mark.parametrize("max_chars", [0, -1])
def test_nonpositive_size_is_rejected(max_chars: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        chunk_text("hello", max_chars=max_chars)


@pytest.mark.parametrize("max_chars", [True, 2.5, "5"])
def test_invalid_size_type_is_rejected(max_chars: object) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        chunk_text("hello", max_chars=max_chars)  # type: ignore[arg-type]


def test_non_string_text_is_rejected() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        chunk_text(None)  # type: ignore[arg-type]
