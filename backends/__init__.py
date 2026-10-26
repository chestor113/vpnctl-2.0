import os

from backends import amneziawg
from backends import wireguard


BACKENDS = {
    "amneziawg": amneziawg,
    "wireguard": wireguard,
}


def get_backend():
    backend_name = os.getenv(
        "VPN_BACKEND",
        "amneziawg",
    ).strip().lower()

    try:
        return BACKENDS[backend_name]
    except KeyError:
        raise ValueError(
            f"Unsupported VPN_BACKEND: {backend_name}"
        )