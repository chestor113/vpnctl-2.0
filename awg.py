import ipaddress
import subprocess


def gen_awg_keys():
    private = subprocess.run(
        ["awg", "genkey"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    public = subprocess.run(
        ["awg", "pubkey"],
        input=private,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    psk = subprocess.run(
        ["awg", "genpsk"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return {
        "private_key": private,
        "public_key": public,
        "preshared_key": psk,
    }


def get_awg_free_ip(network_mask, taken_ips):
    taken = set(ip for ip in taken_ips if ip is not None)
    network = ipaddress.ip_network(network_mask)

    for ip in network.hosts():
        ip_str = str(ip)
        if ip_str == "10.10.0.1":
            continue
        if ip_str not in taken:
            return ip_str

    return None
