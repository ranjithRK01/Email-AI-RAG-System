"""Conservative preparation of plain-text email bodies for retrieval."""


def clean_email_text(body_text: str, *, remove_signature: bool = False) -> str:
    """Normalize plain text, preserving internal spacing and one blank line.

    Signature removal is opt-in: discard an exact '-- ' line and all text
    following it. This heuristic can discard useful content, so callers must
    retain the original body. This is not HTML or prompt-injection sanitization.
    """
    if not isinstance(body_text, str):
        raise TypeError("body_text must be a string")
    normalized = body_text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    for line in normalized.split("\n"):
        # Detect before trimming: the separator's trailing space is significant.
        if remove_signature and line == "-- ":
            break
        line = line if line == "-- " else line.rstrip(" \t")
        if not line and (not cleaned_lines or cleaned_lines[-1] == ""):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()
