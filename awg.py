import ipaddress
import subprocess


def _run_awg(args, input_text=None):
    """
    Run awg command and return stripped stdout.
    """

    try:
        result = subprocess.run(
            ["awg", *args],
            input=input_text,
            capture_output=True,
            text=True,
            check=True,
        )

    except FileNotFoundError as e:
        raise RuntimeError(
            "awg command not found"
        ) from e

    except subprocess.CalledProcessError as e:
        error = (e.stderr or "").strip()

        raise RuntimeError(
            f"awg {' '.join(args)} failed: {error}"
        ) from e

    output = result.stdout.strip()

    if not output:
        raise RuntimeError(
            f"awg {' '.join(args)} returned empty output"
        )

    return output


def gen_awg_keys():
    """
    Generate key material for one AWG peer.
    """

    private_key = _run_awg(
        ["genkey"]
    )

    public_key = _run_awg(
        ["pubkey"],
        input_text=f"{private_key}\n",
    )

    preshared_key = _run_awg(
        ["genpsk"]
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "preshared_key": preshared_key,
    }


def _normalize_ip(value):
    """
    Convert:

        10.10.0.2
        10.10.0.2/24
        10.10.0.2/32

    into:

        10.10.0.2
    """

    value = str(value).strip()

    if "/" in value:
        return ipaddress.ip_interface(value).ip

    return ipaddress.ip_address(value)


def get_awg_free_ip(
    network_mask,
    taken_ips,
    reserved_ips=None,
):
    """
    Return the first free host IP from the VPN network.

    The first usable address is reserved for the AWG server
    unless reserved_ips is explicitly supplied.

    Example:

        network: 10.10.0.0/24

        reserved:
            10.10.0.1

        clients start from:
            10.10.0.2
    """

    network = ipaddress.ip_network(
        network_mask,
        strict=False,
    )

    hosts = network.hosts()

    try:
        first_host = next(hosts)
    except StopIteration:
        return None

    if reserved_ips is None:
        reserved = {first_host}
    else:
        reserved = {
            _normalize_ip(ip)
            for ip in reserved_ips
            if ip is not None
        }

    taken = {
        _normalize_ip(ip)
        for ip in taken_ips
        if ip is not None
    }

    unavailable = taken | reserved

    for ip in network.hosts():
        if ip not in unavailable:
            return str(ip)

    return None