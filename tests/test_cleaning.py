import pytest

from app.cleaning import clean_email_text


def test_clean_text_is_unchanged() -> None:
    text = (
        "We have an opening for a Senior Python Developer. "
        "Are you available for a short introductory call next week?"
    )
    assert clean_email_text(text) == text


def test_internal_spacing_and_paragraphs_are_preserved() -> None:
    text = " \t\r\nInterview:  2026-09-25\n\nTime:\t14:00 UTC.\r\n "
    assert clean_email_text(text) == "Interview:  2026-09-25\n\nTime:\t14:00 UTC."


@pytest.mark.parametrize("text", ["", " \t\r\n"])
def test_empty_or_whitespace_only_body(text: str) -> None:
    assert clean_email_text(text) == ""


def test_cleaning_is_repeatable_and_idempotent() -> None:
    text = "  Salary: USD 100,000.\nRegards, Maya  "
    cleaned = clean_email_text(text)
    assert cleaned == "Salary: USD 100,000.\nRegards, Maya"
    assert clean_email_text(text) == cleaned
    assert clean_email_text(cleaned) == cleaned


@pytest.mark.parametrize("value", [None, 123, ["email"]])
def test_non_string_input_is_rejected(value: object) -> None:
    with pytest.raises(TypeError, match="^body_text must be a string$"):
        clean_email_text(value)  # type: ignore[arg-type]


def test_line_endings_and_excess_blank_lines_are_normalized() -> None:
    text = "Title  \r\n\t\r\n\r\n  - Python\t \rDetails\r\n"
    assert clean_email_text(text) == "Title\n\n  - Python\nDetails"


def test_signature_is_kept_by_default() -> None:
    text = "Interview at 14:00 UTC.\n-- \nMaya\nRecruiter"
    assert clean_email_text(text) == text


def test_explicit_signature_removal_is_optional() -> None:
    text = "Interview at 14:00 UTC.\r\n\r\n-- \r\nMaya\r\nRecruiter"
    assert clean_email_text(text, remove_signature=True) == "Interview at 14:00 UTC."
    assert "Maya" in text  # The source string is unchanged.


@pytest.mark.parametrize("marker", ["Thanks,", "Regards,", "--", "---", "> -- ", "  -- "])
def test_signature_removal_does_not_guess_from_other_markers(marker: str) -> None:
    text = f"Requirements\n{marker}\nPython and PostgreSQL"
    assert "Python and PostgreSQL" in clean_email_text(text, remove_signature=True)


@pytest.mark.parametrize("remove_signature", [False, True])
def test_normalization_remains_idempotent(remove_signature: bool) -> None:
    text = "  Role\r\n\r\n\r\n  - Python  \r\n-- \r\nMaya\r\n"
    once = clean_email_text(text, remove_signature=remove_signature)
    assert clean_email_text(once, remove_signature=remove_signature) == once


def test_signature_only_body_can_be_empty() -> None:
    assert clean_email_text("-- \nMaya", remove_signature=True) == ""
