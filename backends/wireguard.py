from __future__ import annotations

import ipaddress
import os
import subprocess
import tempfile
from pathlib import Path

from result import Result


NAME = "wireguard"

NETWORK = os.getenv(
    "VPN_NETWORK",
    "10.10.0.0/24",
)

INTERFACE = os.getenv(
    "WG_INTERFACE",
    "wg0",
)

CONFIG_DIR = Path(
    os.getenv(
        "WG_CONFIG_DIR",
        "/etc/wireguard",
    )
)

BASE_CONFIG_PATH = CONFIG_DIR / f"{INTERFACE}.base.conf"
SERVER_CONFIG_PATH = CONFIG_DIR / f"{INTERFACE}.conf"

CLIENT_CONFIG_FILENAME = "wg.conf"

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output"


def _run(
    command: list[str],
    *,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )

    return result.stdout.strip()


def generate_keys() -> dict[str, str]:
    private_key = _run(["wg", "genkey"])

    public_key = _run(
        ["wg", "pubkey"],
        input_text=private_key + "\n",
    )

    preshared_key = _run(
        ["wg", "genpsk"],
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "preshared_key": preshared_key,
    }


def get_free_ip(
    used_ips: list[str],
) -> str | None:
    network = ipaddress.ip_network(
        NETWORK,
        strict=False,
    )

    used = {
        ipaddress.ip_address(
            str(ip).split("/")[0]
        )
        for ip in used_ips
        if ip
    }

    server_ip = network.network_address + 1

    for candidate in network.hosts():
        if candidate == server_ip:
            continue

        if candidate in used:
            continue

        return str(candidate)

    return None


def render_client_config(
    data: dict,
) -> str:
    preshared_key = data.get(
        "preshared_key"
    )

    lines = [
        "[Interface]",
        f"PrivateKey = {data['client_pr_key']}",
        f"Address = {data['client_ip']}/32",
        f"DNS = {data['dns']}",
        "",
        "[Peer]",
        f"PublicKey = {data['server_pub_key']}",
    ]

    if preshared_key:
        lines.append(
            f"PresharedKey = {preshared_key}"
        )

    lines.extend(
        [
            f"Endpoint = {data['endpoint']}",
            "AllowedIPs = 0.0.0.0/0, ::/0",
            "PersistentKeepalive = 25",
            "",
        ]
    )

    return "\n".join(lines)


def save_client_config(
    config_text: str,
    dir_name: str,
) -> Path:
    output_dir = OUTPUT_DIR / dir_name
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        output_dir
        / CLIENT_CONFIG_FILENAME
    )

    path.write_text(
        config_text,
        encoding="utf-8",
    )

    path.chmod(0o600)

    return path


def build_server_config(
    peers: list[dict],
) -> str:
    base_config = (
        BASE_CONFIG_PATH
        .read_text(encoding="utf-8")
        .rstrip()
    )

    sections = [base_config]

    for peer in peers:
        peer_lines = [
            "",
            "[Peer]",
            f"# {peer.get('telegram') or peer.get('device_uuid')}",
            f"PublicKey = {peer['wg_public_key']}",
        ]

        preshared_key = peer.get(
            "wg_preshared_key"
        )

        if preshared_key:
            peer_lines.append(
                f"PresharedKey = {preshared_key}"
            )

        peer_lines.append(
            f"AllowedIPs = {peer['wg_assigned_ip']}/32"
        )

        sections.append(
            "\n".join(peer_lines)
        )

    return "\n".join(sections) + "\n"


def save_server_config(
    config_text: str,
) -> Path:
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SERVER_CONFIG_PATH.write_text(
        config_text,
        encoding="utf-8",
    )

    SERVER_CONFIG_PATH.chmod(0o600)

    return SERVER_CONFIG_PATH


def _interface_exists() -> bool:
    result = subprocess.run(
        [
            "ip",
            "link",
            "show",
            INTERFACE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return result.returncode == 0


def _sync_running_interface() -> None:
    stripped_config = _run(
        [
            "wg-quick",
            "strip",
            str(SERVER_CONFIG_PATH),
        ]
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(stripped_config)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    try:
        subprocess.run(
            [
                "wg",
                "syncconf",
                INTERFACE,
                str(tmp_path),
            ],
            check=True,
        )
    finally:
        tmp_path.unlink(
            missing_ok=True
        )


def deploy_server_config() -> Result:
    try:
        if _interface_exists():
            _sync_running_interface()

            action = "synced"

        else:
            subprocess.run(
                [
                    "wg-quick",
                    "up",
                    str(SERVER_CONFIG_PATH),
                ],
                check=True,
            )

            action = "started"

        return Result(
            True,
            data={
                "vpn_backend": NAME,
                "interface": INTERFACE,
                "deploy_action": action,
                "server_config": (
                    SERVER_CONFIG_PATH.as_posix()
                ),
            },
        )

    except Exception as exc:
        return Result(
            False,
            error=(
                "WireGuard deploy failed: "
                f"{exc}"
            ),
        )