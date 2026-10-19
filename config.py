from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SECRETS_DIR = PROJECT_DIR / "secrets"

SERVER_PUBLIC_KEY_FILE = (
    SECRETS_DIR
    / "wg_server_public.key"
)

ENDPOINT_FILE = (
    SECRETS_DIR
    / "wg_endpoint.txt"
)


def _read_text_file(path: Path) -> str:
    """
    Read required text value from a file.
    """

    try:
        value = path.read_text(
            encoding="utf-8"
        ).strip()

    except FileNotFoundError as e:
        raise RuntimeError(
            f"Required config file not found: {path}"
        ) from e

    except PermissionError as e:
        raise RuntimeError(
            f"Permission denied reading config file: {path}"
        ) from e

    if not value:
        raise RuntimeError(
            f"Config file is empty: {path}"
        )

    return value


def get_server_public_key() -> str:
    return _read_text_file(
        SERVER_PUBLIC_KEY_FILE
    )


def get_endpoint() -> str:
    return _read_text_file(
        ENDPOINT_FILE
    )