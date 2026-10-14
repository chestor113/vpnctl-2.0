from pathlib import Path


def read_text_file(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"File is empty: {path}")
    return value


def get_server_public_key() -> str:
    return read_text_file("secrets/awg_server_public.key")


def get_server_private_key() -> str:
    return read_text_file("secrets/awg_server_private.key")


def get_endpoint() -> str:
    return read_text_file("secrets/awg_endpoint.txt")
