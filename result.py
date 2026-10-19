from typing import Any


class Result:
    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: str | None = None,
    ):
        self.success = success
        self.data = data
        self.error = error

    def __bool__(self) -> bool:
        return self.success