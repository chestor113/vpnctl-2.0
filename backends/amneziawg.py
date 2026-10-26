from pathlib import Path

import awg
import awg_config
import awg_server_config
import deploy


NAME = "amneziawg"

NETWORK = "10.10.0.0/24"

BASE_CONFIG_PATH = Path(
    "/etc/amnezia/amneziawg/awg0.base.conf"
)

CLIENT_CONFIG_FILENAME = "awg.conf"
SERVER_CONFIG_FILENAME = "awg0.conf"


def generate_keys():
    return awg.gen_awg_keys()


def get_free_ip(used_ips):
    return awg.get_awg_free_ip(
        NETWORK,
        used_ips,
    )


def render_client_config(data):
    return awg_config.render_client_config(data)


def save_client_config(config_text, dir_name):
    return awg_config.save_client_config(
        config_text,
        dir_name,
        CLIENT_CONFIG_FILENAME,
    )


def build_server_config(peers):
    return awg_server_config.build_server_config(
        base_config_path=BASE_CONFIG_PATH,
        peers=peers,
    )


def save_server_config(config_text):
    return awg_server_config.save_awg_server_conf(
        config_text,
        SERVER_CONFIG_FILENAME,
    )


def deploy_server_config():
    return deploy.deploy_server_config()