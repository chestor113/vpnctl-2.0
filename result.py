from dataclasses import dataclass

@dataclass
class Result:
    ok: bool
    data: dict | None = None
    error: str | None = None

    def __bool__(self):
        return self.ok