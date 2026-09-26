"""A minimal character-based baseline for splitting cleaned email text."""


def chunk_text(text: str, *, max_chars: int = 500) -> list[str]:
    """Return consecutive, non-overlapping slices without dropping characters.

    Sizes count Python Unicode code points, not model tokens. Boundaries may
    split words or sentences; this baseline is not a semantic chunker.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if isinstance(max_chars, bool) or not isinstance(max_chars, int):
        raise TypeError("max_chars must be an integer")
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    return [text[start : start + max_chars] for start in range(0, len(text), max_chars)]
