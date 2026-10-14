from pathlib import Path


def render_client_config(data):
    result = f"""[Interface]
PrivateKey = {data['client_pr_key']}
Address = {data['client_ip']}/32
DNS = {data['dns']}

Jc = 7
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

I1 = <r 2><b 0x858000010002000000001c><rc 28><b 0x0463646e730669636c6f756403636f6d0000010001c00c000100010000003c00043c263e6bc00c000100010000003c000475bb065f>

[Peer]
PublicKey = {data['server_pub_key']}
PresharedKey = {data['preshared_key']}
Endpoint = {data['endpoint']}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
    return result


def save_client_config(config_text, dir_name, filename):
    path = Path("output") / dir_name / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(config_text)

    return path


def render_server_peer(data):
    result = f"""[Peer]
# friendly_name={data['telegram']}
PublicKey = {data['client_pub_key']}
PresharedKey = {data['preshared_key']}
AllowedIPs = {data['client_ip']}/32

"""
    return result


def save_peer_config(config_text, dir_name, filename):
    path = Path("amneziawg/peers") / dir_name / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(config_text)

    return path
