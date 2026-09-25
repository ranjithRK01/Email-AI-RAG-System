from typing import Any, Protocol


class EmailRepository(Protocol):
    def list_all(self) -> list[dict[str, Any]]: ...

    def find_by_id(self, email_id: str) -> dict[str, Any] | None: ...
