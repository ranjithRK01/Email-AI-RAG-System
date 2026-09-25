class EmailNotFoundError(Exception):
    """The requested email does not exist."""


class InvalidEmailQueryError(Exception):
    """Email search options violate the application's query rules."""
