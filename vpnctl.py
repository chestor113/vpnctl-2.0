import logging
import sys
from typing import Any

import cli
from logger_config import setup_logging


logger = logging.getLogger(__name__)


SENSITIVE_KEYS = {
    "wg_private_key",
    "wg_preshared_key",
    "private_key",
    "preshared_key",
    "client_pr_key",
}


def _safe_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Hide sensitive key material from CLI output.
    """

    return {
        key: (
            "<hidden>"
            if key in SENSITIVE_KEYS and value
            else value
        )
        for key, value in data.items()
    }


def print_result_data(data: Any) -> None:
    if data is None:
        return

    if isinstance(data, dict):
        safe_data = _safe_dict(data)

        for key, value in safe_data.items():
            print(f"{key}: {value}")

        return

    if isinstance(data, list):
        if not data:
            print("No data")
            return

        for index, item in enumerate(
            data,
            start=1,
        ):
            if isinstance(item, dict):
                safe_item = _safe_dict(item)

                if len(data) > 1:
                    print(f"[{index}]")

                for key, value in safe_item.items():
                    print(f"{key}: {value}")

                if index < len(data):
                    print()

            else:
                print(item)

        return

    print(data)


def main() -> int:
    setup_logging()

    parser = cli.build_parser()

    argv = sys.argv[1:]

    if argv:
        argv[0] = argv[0].lower()

    args = parser.parse_args(argv)

    try:
        result = args.handler(args)

    except KeyboardInterrupt:
        print("\nInterrupted")
        logger.warning(
            "Operation interrupted by user"
        )
        return 130

    except Exception:
        logger.exception(
            "Unhandled vpnctl error"
        )

        print(
            "ERROR: unexpected internal error"
        )

        return 1

    if not result:
        error = (
            result.error
            or "Operation failed"
        )

        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )

        logger.error(
            "Operation failed: %s",
            error,
        )

        if result.data is not None:
            print_result_data(
                result.data
            )

        return 1

    if result.data is not None:
        print_result_data(
            result.data
        )

    logger.info(
        "Operation completed successfully"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())