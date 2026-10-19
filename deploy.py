from pathlib import Path
import logging
import subprocess

from result import Result


logger = logging.getLogger(__name__)


PROJECT_DIR = Path(__file__).resolve().parent

AWG_INTERFACE = "awg0"

GENERATED_CONFIG = (
    PROJECT_DIR
    / "amneziawg"
    / "server_config"
    / "awg0.conf"
)

SYSTEM_CONFIG = Path(
    "/etc/amnezia/amneziawg/awg0.conf"
)


def _run(
    command,
    *,
    input_text=None,
    sudo=False,
):
    """
    Run a command and return CompletedProcess.

    sudo=True uses non-interactive sudo.
    If sudo permissions are missing, command fails
    instead of waiting for a password.
    """

    cmd = list(command)

    if sudo:
        cmd = [
            "sudo",
            "-n",
            *cmd,
        ]

    try:
        return subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            check=True,
        )

    except FileNotFoundError as e:
        raise RuntimeError(
            f"Command not found: {cmd[0]}"
        ) from e

    except subprocess.CalledProcessError as e:
        stderr = (
            e.stderr
            or e.stdout
            or ""
        ).strip()

        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}"
            + (
                f": {stderr}"
                if stderr
                else ""
            )
        ) from e


def _strip_config(config_path):
    """
    Convert awg-quick config into a config
    suitable for `awg syncconf`.

    awg-quick configs may contain things such as:
        Address
        DNS
        PostUp
        PostDown

    `awg syncconf` does not accept those directly.
    """

    result = _run(
        [
            "awg-quick",
            "strip",
            str(config_path),
        ]
    )

    stripped = result.stdout.strip()

    if not stripped:
        raise RuntimeError(
            "awg-quick strip returned empty config"
        )

    return stripped + "\n"


def _install_system_config(source):
    """
    Install persistent config used after reboot.

    The config contains the server private key,
    therefore permissions are 0600.
    """

    _run(
        [
            "install",
            "-o",
            "root",
            "-g",
            "root",
            "-m",
            "0600",
            str(source),
            str(SYSTEM_CONFIG),
        ],
        sudo=True,
    )


def _sync_runtime_config(stripped_config):
    """
    Apply AWG peer/config changes to the running
    interface without restarting the interface.
    """

    _run(
        [
            "awg",
            "syncconf",
            AWG_INTERFACE,
            "/dev/stdin",
        ],
        input_text=stripped_config,
        sudo=True,
    )


def deploy_server_config() -> Result:
    """
    Validate, apply and persist generated AWG config.

    Order:

        generated config
        -> awg-quick strip
        -> awg syncconf
        -> install persistent awg0.conf

    No awg-quick down/up is performed.
    """

    try:
        if not GENERATED_CONFIG.exists():
            return Result(
                False,
                error=(
                    "Generated AWG config not found: "
                    f"{GENERATED_CONFIG}"
                ),
            )

        if GENERATED_CONFIG.stat().st_size == 0:
            return Result(
                False,
                error="Generated AWG config is empty",
            )

        # First parse/validate the generated config.
        stripped_config = _strip_config(
            GENERATED_CONFIG
        )

        # Apply it to the running interface.
        _sync_runtime_config(
            stripped_config
        )

        # Only after successful runtime apply do we
        # make the config persistent for reboot.
        _install_system_config(
            GENERATED_CONFIG
        )

        logger.info(
            "AWG config deployed: interface=%s config=%s",
            AWG_INTERFACE,
            SYSTEM_CONFIG,
        )

        return Result(
            True,
            data={
                "interface": AWG_INTERFACE,
                "system_config": str(
                    SYSTEM_CONFIG
                ),
                "deploy_mode": "syncconf",
            },
        )

    except Exception as e:
        logger.exception(
            "Failed to deploy AWG server config"
        )

        return Result(
            False,
            error=str(e),
        )