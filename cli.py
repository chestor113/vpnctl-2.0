import argparse

import services


DEFAULT_ACCESS_DAYS = 180
DEFAULT_ACCESS_TAG = "regular"
DEFAULT_DEVICE_TAG = "phone"


def _add_telegram_argument(parser):
    parser.add_argument(
        "-t",
        "--telegram",
        required=True,
        help="Telegram username",
    )


def _add_device_selector(parser):
    selector = parser.add_mutually_exclusive_group(
        required=True
    )

    selector.add_argument(
        "--device",
        help="Device tag, for example: phone, laptop, desktop",
    )

    selector.add_argument(
        "--device-uuid",
        help="Device UUID",
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vpnctl",
        description="Manage VPN access",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # ------------------------------------------------------------------
    # Create user
    # ------------------------------------------------------------------

    create_parser = subparsers.add_parser(
        "create",
        help="Create user and first VPN device",
    )

    create_parser.add_argument(
        "-u",
        "--username",
        required=True,
        help="User name",
    )

    _add_telegram_argument(
        create_parser
    )

    create_parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=DEFAULT_ACCESS_DAYS,
        help=(
            "Access duration for regular users "
            f"(default: {DEFAULT_ACCESS_DAYS} days)"
        ),
    )

    create_parser.add_argument(
        "--tag",
        default=DEFAULT_ACCESS_TAG,
        help=(
            "Access tag. 'regular' is temporary; "
            "any other tag is permanent "
            f"(default: {DEFAULT_ACCESS_TAG})"
        ),
    )

    create_parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE_TAG,
        help=(
            "First device tag "
            f"(default: {DEFAULT_DEVICE_TAG})"
        ),
    )

    create_parser.set_defaults(
        handler=services.handle_create
    )

    # ------------------------------------------------------------------
    # Renew user
    # ------------------------------------------------------------------

    renew_parser = subparsers.add_parser(
        "renew",
        help="Extend regular user access",
    )

    _add_telegram_argument(
        renew_parser
    )

    renew_parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=DEFAULT_ACCESS_DAYS,
        help=(
            "Days to add "
            f"(default: {DEFAULT_ACCESS_DAYS})"
        ),
    )

    renew_parser.set_defaults(
        handler=services.handle_renew
    )

    # ------------------------------------------------------------------
    # Disable user
    # ------------------------------------------------------------------

    disable_parser = subparsers.add_parser(
        "disable",
        help="Disable user access",
    )

    _add_telegram_argument(
        disable_parser
    )

    disable_parser.set_defaults(
        handler=services.handle_disable
    )

    # ------------------------------------------------------------------
    # Enable user
    # ------------------------------------------------------------------

    enable_parser = subparsers.add_parser(
        "enable",
        help="Enable user access",
    )

    _add_telegram_argument(
        enable_parser
    )

    enable_parser.set_defaults(
        handler=services.handle_enable
    )

    # ------------------------------------------------------------------
    # List users
    # ------------------------------------------------------------------

    list_parser = subparsers.add_parser(
        "list",
        help="List users",
    )

    list_filter = (
        list_parser.add_mutually_exclusive_group()
    )

    list_filter.add_argument(
        "--all",
        action="store_true",
        help="Show all users",
    )

    list_filter.add_argument(
        "-a",
        "--active",
        action="store_true",
        help="Show enabled users",
    )

    list_filter.add_argument(
        "-i",
        "--inactive",
        action="store_true",
        help="Show disabled users",
    )

    list_parser.set_defaults(
        handler=services.handle_list
    )

    # ------------------------------------------------------------------
    # Delete user
    # ------------------------------------------------------------------

    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete user and all their devices",
    )

    _add_telegram_argument(
        delete_parser
    )

    delete_parser.set_defaults(
        handler=services.handle_delete
    )

    # ------------------------------------------------------------------
    # Expire users
    # ------------------------------------------------------------------

    expire_parser = subparsers.add_parser(
        "expire",
        help="Disable expired regular users",
    )

    expire_parser.set_defaults(
        handler=services.handle_expired
    )

    # ==================================================================
    # Devices
    # ==================================================================

    # ------------------------------------------------------------------
    # Add device
    # ------------------------------------------------------------------

    device_add_parser = subparsers.add_parser(
        "device-add",
        help="Add VPN device to existing user",
    )

    _add_telegram_argument(
        device_add_parser
    )

    device_add_parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE_TAG,
        help=(
            "Device tag "
            f"(default: {DEFAULT_DEVICE_TAG})"
        ),
    )

    device_add_parser.set_defaults(
        handler=services.handle_device_add
    )

    # ------------------------------------------------------------------
    # List devices
    # ------------------------------------------------------------------

    device_list_parser = subparsers.add_parser(
        "device-list",
        help="List user's VPN devices",
    )

    _add_telegram_argument(
        device_list_parser
    )

    device_list_parser.set_defaults(
        handler=services.handle_device_list
    )

    # ------------------------------------------------------------------
    # Disable device
    # ------------------------------------------------------------------

    device_disable_parser = subparsers.add_parser(
        "device-disable",
        help="Disable one VPN device",
    )

    _add_telegram_argument(
        device_disable_parser
    )

    _add_device_selector(
        device_disable_parser
    )

    device_disable_parser.set_defaults(
        handler=services.handle_device_disable
    )

    # ------------------------------------------------------------------
    # Enable device
    # ------------------------------------------------------------------

    device_enable_parser = subparsers.add_parser(
        "device-enable",
        help="Enable one VPN device",
    )

    _add_telegram_argument(
        device_enable_parser
    )

    _add_device_selector(
        device_enable_parser
    )

    device_enable_parser.set_defaults(
        handler=services.handle_device_enable
    )

    # ------------------------------------------------------------------
    # Delete device
    # ------------------------------------------------------------------

    device_delete_parser = subparsers.add_parser(
        "device-delete",
        help="Delete one VPN device",
    )

    _add_telegram_argument(
        device_delete_parser
    )

    _add_device_selector(
        device_delete_parser
    )

    device_delete_parser.set_defaults(
        handler=services.handle_device_delete
    )

    return parser
