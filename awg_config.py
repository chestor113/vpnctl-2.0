from ipaddress import ip_address, ip_interface
from pathlib import Path
import os
import tempfile


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"


AWG_CLIENT_PARAMS = """Jc = 7
Jmin = 40
Jmax = 900

S1 = 96
S2 = 73
S3 = 32
S4 = 16

H1 = 120000000-129999999
H2 = 520000000-529999999
H3 = 1120000000-1129999999
H4 = 1820000000-1829999999

I1 = <r 2><b 0x858000010002000000001c><rc 28><b 0x0463646e730669636c6f756403636f6d0000010001c00c000100010000003c00043c263e6bc00c000100010000003c000475bb065f>"""


def _require(data, key):
    value = data.get(key)

    if value is None or str(value).strip() == "":
        raise ValueError(
            f"Missing required config value: {key}"
        )

    return str(value).strip()


def _normalize_client_address(value):
    """
    Convert:

        10.10.0.2
        10.10.0.2/24
        10.10.0.2/32

    into:

        10.10.0.2/32
    """

    value = str(value).strip()

    if "/" in value:
        address = ip_interface(value).ip
    else:
        address = ip_address(value)

    prefix = 32 if address.version == 4 else 128

    return f"{address}/{prefix}"


def render_client_config(data):
    private_key = _require(
        data,
        "client_pr_key",
    )

    client_ip = _normalize_client_address(
        _require(
            data,
            "client_ip",
        )
    )

    server_public_key = _require(
        data,
        "server_pub_key",
    )

    endpoint = _require(
        data,
        "endpoint",
    )

    dns = _require(
        data,
        "dns",
    )

    preshared_key = data.get(
        "preshared_key"
    )

    peer_lines = [
        "[Peer]",
        f"PublicKey = {server_public_key}",
    ]

    if preshared_key:
        peer_lines.append(
            f"PresharedKey = {preshared_key}"
        )

    peer_lines.extend(
        [
            f"Endpoint = {endpoint}",
            "AllowedIPs = 0.0.0.0/0",
            "PersistentKeepalive = 25",
        ]
    )

    peer_config = "\n".join(
        peer_lines
    )

    return (
        "[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {client_ip}\n"
        f"DNS = {dns}\n\n"
        f"{AWG_CLIENT_PARAMS}\n\n"
        f"{peer_config}\n"
    )


def save_client_config(
    config_text,
    dir_name,
    filename="awg.conf",
):
    """
    Save client config atomically.

    Client configs contain private keys,
    so directory permissions are 0700
    and file permissions are 0600.
    """

    if not config_text:
        raise ValueError(
            "Client config is empty"
        )

    if Path(dir_name).name != dir_name:
        raise ValueError(
            "dir_name must not contain a path"
        )

    if Path(filename).name != filename:
        raise ValueError(
            "filename must not contain a path"
        )

    device_dir = (
        OUTPUT_DIR
        / dir_name
    )

    device_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.chmod(
        device_dir,
        0o700,
    )

    target = (
        device_dir
        / filename
    )

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{filename}.",
        dir=device_dir,
        text=True,
    )

    try:
        os.fchmod(
            fd,
            0o600,
        )

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(
                config_text
            )

            file.flush()
            os.fsync(
                file.fileno()
            )

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
            os.unlink(
                temp_name
            )
        except FileNotFoundError:
            pass

        raise

    return target