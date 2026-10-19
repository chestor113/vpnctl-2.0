from ipaddress import ip_address, ip_interface
from pathlib import Path
import logging
import os
import subprocess
import tempfile


logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
SERVER_CONFIG_DIR = PROJECT_DIR / "amneziawg" / "server_config"


def _read_base_config(base_config_path):
    """
    Read AWG base config.

    Base config may be root-only, so if normal read fails
    try sudo without asking for a password.
    """

    path = Path(base_config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"AWG base config not found: {path}"
        )

    try:
        return path.read_text(encoding="utf-8")

    except PermissionError:
        completed = subprocess.run(
            [
                "sudo",
                "-n",
                "cat",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return completed.stdout


def _normalize_allowed_ip(value):
    """
    Convert stored device IP into host AllowedIPs format.

    Examples:

        10.10.0.2
        -> 10.10.0.2/32

        10.10.0.2/24
        -> 10.10.0.2/32

        10.10.0.2/32
        -> 10.10.0.2/32
    """

    value = str(value).strip()

    if not value:
        raise ValueError("Empty peer IP")

    if "/" in value:
        address = ip_interface(value).ip
    else:
        address = ip_address(value)

    prefix = 32 if address.version == 4 else 128

    return f"{address}/{prefix}"


def _safe_comment(value):
    if value is None:
        return ""

    return (
        str(value)
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def _render_peer(peer):
    """
    Render one AWG server peer from DB data.

    Server config intentionally never contains
    the client's private key.
    """

    public_key = peer.get("wg_public_key")
    assigned_ip = peer.get("wg_assigned_ip")

    if not public_key:
        raise ValueError(
            f"Peer {peer.get('device_uuid')} has no public key"
        )

    if not assigned_ip:
        raise ValueError(
            f"Peer {peer.get('device_uuid')} has no assigned IP"
        )

    allowed_ip = _normalize_allowed_ip(assigned_ip)

    username = _safe_comment(peer.get("username"))
    device_tag = _safe_comment(peer.get("device_tag"))
    device_uuid = _safe_comment(peer.get("device_uuid"))

    label_parts = [
        part
        for part in (
            username,
            device_tag,
            device_uuid,
        )
        if part
    ]

    lines = []

    if label_parts:
        lines.append(
            "# " + " / ".join(label_parts)
        )

    lines.extend(
        [
            "[Peer]",
            f"PublicKey = {public_key}",
        ]
    )

    preshared_key = peer.get("wg_preshared_key")

    if preshared_key:
        lines.append(
            f"PresharedKey = {preshared_key}"
        )

    lines.append(
        f"AllowedIPs = {allowed_ip}"
    )

    return "\n".join(lines)


def build_server_config(base_config_path, peers):
    """
    Build full AWG server config:

        base [Interface]
        +
        active peers from SQLite
    """

    base_config = _read_base_config(
        base_config_path
    ).strip()

    if not base_config:
        raise ValueError(
            "AWG base config is empty"
        )

    if "[Interface]" not in base_config:
        raise ValueError(
            "AWG base config has no [Interface] section"
        )

    parts = [base_config]

    for peer in peers:
        parts.append(
            _render_peer(peer)
        )

    return "\n\n".join(parts).rstrip() + "\n"


def save_awg_server_conf(
    config_text,
    filename="awg0.conf",
):
    """
    Save generated server config atomically.

    The file contains the server private key inherited
    from the base config, therefore permissions are 0600.
    """

    if not config_text:
        raise ValueError(
            "Server config is empty"
        )

    filename_path = Path(filename)

    if filename_path.name != filename:
        raise ValueError(
            "filename must not contain a path"
        )

    SERVER_CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.chmod(
        SERVER_CONFIG_DIR,
        0o700,
    )

    target = SERVER_CONFIG_DIR / filename

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{filename}.",
        dir=SERVER_CONFIG_DIR,
        text=True,
    )

    try:
        os.fchmod(fd, 0o600)

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(config_text)
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temp_name,
            target,
        )

        os.chmod(
            target,
            0o600,
        )

    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

        raise

    logger.info(
        "AWG server config saved: %s",
        target,
    )

    return target