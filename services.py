from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any
import logging
import shutil
import uuid

import awg
import awg_config
import awg_server_config
import config
import db
import deploy

from result import Result


logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"

AWG_NETWORK = "10.10.0.0/24"
AWG_BASE_CONFIG = Path("/etc/amnezia/amneziawg/awg0.base.conf")

DEFAULT_DNS = "8.8.8.8"
DEFAULT_DEVICE_TAG = "phone"
REGULAR_ACCESS_TAG = "regular"
DEFAULT_ACCESS_DAYS = 180
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _result_dict(result: Result) -> dict[str, Any]:
    if isinstance(result.data, dict):
        return result.data
    return {}


def _safe_name(value: Any) -> str:
    value = str(value or "")
    return "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    )


def _normalize_access_tag(value: Any) -> str:
    tag = str(value or REGULAR_ACCESS_TAG).strip().lower()
    return tag or REGULAR_ACCESS_TAG


def _device_tag_from_args(args: Any) -> str:
    tag = (
        getattr(args, "device", None)
        or getattr(args, "device_tag", None)
        or DEFAULT_DEVICE_TAG
    )
    tag = str(tag).strip()
    return tag or DEFAULT_DEVICE_TAG


def _parse_db_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.strptime(str(value), DATETIME_FORMAT).replace(tzinfo=UTC)


def _regular_access_expired(user: dict[str, Any]) -> bool:
    if user.get("access_tag") != REGULAR_ACCESS_TAG:
        return False
    expires_at = _parse_db_datetime(user.get("expires_at"))
    if expires_at is None:
        return True
    return expires_at <= datetime.now(UTC)


def get_user_by_telegram(tg: str) -> Result:
    if not tg:
        logger.error("Telegram is required")
        return Result(False, error="Telegram is required")

    row = db.get_grant_by_telegram(tg)
    if row is None:
        logger.warning("User not found: telegram=%s", tg)
        return Result(False, error=f"User not found: telegram={tg}")

    return Result(True, data=row)


def _device_dir_name(user: dict[str, Any], device: dict[str, Any]) -> str:
    owner = _safe_name(user.get("telegram") or user["uuid"])
    tag = _safe_name(device["device_tag"])
    short_uuid = str(device["uuid"]).split("-")[0]
    return f"{owner}_{tag}_{short_uuid}"


def _client_awg_data(user: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_pub_key": device["wg_public_key"],
        "client_pr_key": device["wg_private_key"],
        "preshared_key": device.get("wg_preshared_key"),
        "client_ip": device["wg_assigned_ip"],
        "server_pub_key": config.get_server_public_key(),
        "endpoint": config.get_endpoint(),
        "telegram": user.get("telegram"),
        "dns": DEFAULT_DNS,
    }


def _save_client_config(user: dict[str, Any], device: dict[str, Any]) -> Path:
    awg_data = _client_awg_data(user, device)
    client_config = awg_config.render_client_config(awg_data)
    dir_name = _device_dir_name(user, device)
    return awg_config.save_client_config(client_config, dir_name, "awg.conf")


def _remove_device_output(user: dict[str, Any], device: dict[str, Any]) -> None:
    path = OUTPUT_DIR / _device_dir_name(user, device)
    if path.exists():
        shutil.rmtree(path)


def _get_device_for_user(args: Any, user: dict[str, Any]) -> Result:
    device_uuid = getattr(args, "device_uuid", None)

    if device_uuid:
        device = db.get_device_by_uuid(device_uuid)
        if device is None:
            return Result(False, error=f"Device not found: uuid={device_uuid}")
        if device["access_grant_uuid"] != user["uuid"]:
            return Result(False, error="Device does not belong to this user")
        return Result(True, data=device)

    device_tag = getattr(args, "device", None) or getattr(args, "device_tag", None)
    if not device_tag:
        return Result(False, error="Device tag or device UUID is required")

    device = db.get_device_by_tag(user["uuid"], str(device_tag))
    if device is None:
        return Result(False, error=f"Device not found: {device_tag}")

    return Result(True, data=device)


def rebuild_server_awg_config() -> Result:
    try:
        peers = db.get_active_awg_peers()
        server_config = awg_server_config.build_server_config(
            base_config_path=AWG_BASE_CONFIG,
            peers=peers,
        )
        path_config = awg_server_config.save_awg_server_conf(
            server_config,
            "awg0.conf",
        )
        return Result(
            True,
            data={
                "srv_path_config": path_config.as_posix(),
                "active_peers": len(peers),
            },
        )
    except Exception:
        logger.exception("Can't rebuild AWG server config")
        return Result(False, error="Failed to rebuild server config")


def rebuild_and_deploy() -> Result:
    config_result = rebuild_server_awg_config()
    if not config_result:
        return config_result

    deploy_result = deploy.deploy_server_config()
    if not deploy_result:
        return deploy_result

    return Result(
        True,
        data={
            **_result_dict(config_result),
            **_result_dict(deploy_result),
        },
    )


def map_db_to_config() -> list[dict[str, Any]]:
    return [
        {
            "id": row["device_uuid"],
            "email": row["telegram"] or row["grant_uuid"],
        }
        for row in db.get_active_awg_peers()
    ]


def handle_create(args: Any) -> Result:
    try:
        telegram = str(args.telegram).strip()
        username = str(args.username).strip()

        if not telegram:
            return Result(False, error="Telegram is required")
        if not username:
            return Result(False, error="Username is required")
        if db.get_grant_by_telegram(telegram):
            return Result(False, error="User already exists")

        access_tag = _normalize_access_tag(
            getattr(args, "tag", REGULAR_ACCESS_TAG)
        )
        created_at = datetime.now(UTC)

        if access_tag == REGULAR_ACCESS_TAG:
            days = int(getattr(args, "days", DEFAULT_ACCESS_DAYS))
            if days <= 0:
                return Result(
                    False,
                    error="Days must be greater than zero for regular access",
                )
            expires_at = created_at + timedelta(days=days)
        else:
            days = None
            expires_at = None

        device_tag = _device_tag_from_args(args)
        awg_keys = awg.gen_awg_keys()
        awg_ip = awg.get_awg_free_ip(
            AWG_NETWORK,
            db.get_used_ip_addresses(),
        )

        if awg_ip is None:
            return Result(False, error="No free AmneziaWG IP available")

        grant_uuid = str(uuid.uuid4())
        device_uuid = str(uuid.uuid4())

        grant_payload = {
            "uuid": grant_uuid,
            "username": username,
            "telegram": telegram,
            "created_at": created_at,
            "expires_at": expires_at,
            "is_enabled": 1,
            "access_tag": access_tag,
        }

        device_payload = {
            "uuid": device_uuid,
            "device_tag": device_tag,
            "created_at": created_at,
            "is_enabled": 1,
            "wg_public_key": awg_keys["public_key"],
            "wg_private_key": awg_keys["private_key"],
            "wg_preshared_key": awg_keys.get("preshared_key"),
            "wg_assigned_ip": awg_ip,
        }

        created = db.create_grant_with_first_device(
            grant_payload,
            device_payload,
        )
        if created is None:
            return Result(False, error="Failed to create user and device in DB")

        user = db.get_grant_by_uuid(grant_uuid)
        device = db.get_device_by_uuid(device_uuid)
        if user is None or device is None:
            db.delete_grant_by_uuid(grant_uuid)
            return Result(False, error="Created data could not be read back from DB")

        try:
            config_path = _save_client_config(user, device)
        except Exception:
            logger.exception("Failed to create client config for %s", device_uuid)
            db.delete_grant_by_uuid(grant_uuid)
            return Result(False, error="Failed to create client configuration")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return Result(
                False,
                data={
                    "grant_uuid": grant_uuid,
                    "device_uuid": device_uuid,
                    "config_path": config_path.as_posix(),
                },
                error=runtime_result.error,
            )

        logger.info(
            "Create success: user=%s telegram=%s tag=%s device=%s ip=%s",
            username,
            telegram,
            access_tag,
            device_tag,
            awg_ip,
        )

        return Result(
            True,
            data={
                "grant_uuid": grant_uuid,
                "device_uuid": device_uuid,
                "username": username,
                "telegram": telegram,
                "access_tag": access_tag,
                "device_tag": device_tag,
                "expires_at": (
                    expires_at.strftime(DATETIME_FORMAT)
                    if expires_at
                    else None
                ),
                "days": days,
                "awg_ip": awg_ip,
                "config_path": config_path.as_posix(),
                **_result_dict(runtime_result),
            },
        )

    except (TypeError, ValueError):
        return Result(False, error="Invalid create arguments")
    except Exception:
        logger.exception(
            "Handle create crashed: username=%s telegram=%s",
            getattr(args, "username", None),
            getattr(args, "telegram", None),
        )
        return Result(False, error="Unexpected error during create")


def handle_disable(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        if not db.set_grant_enabled(user["uuid"], False, "manual"):
            return Result(False, error="Failed to disable user in DB")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        updated = db.get_grant_by_uuid(user["uuid"])
        if updated is None:
            return Result(False, error="User was disabled but could not be read back")

        return Result(
            True,
            data={
                **updated,
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Disable failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during disable")


def handle_enable(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        if _regular_access_expired(user):
            return Result(False, error="Regular access is expired; renew it instead")

        if not db.set_grant_enabled(user["uuid"], True):
            return Result(False, error="Failed to enable user in DB")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        updated = db.get_grant_by_uuid(user["uuid"])
        if updated is None:
            return Result(False, error="User was enabled but could not be read back")

        return Result(
            True,
            data={
                **updated,
                **_result_dict(runtime_result),
            },
        )
    except ValueError:
        return Result(False, error="Invalid expiration date in DB")
    except Exception:
        logger.exception("Enable failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during enable")


def handle_renew(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        if user.get("access_tag") != REGULAR_ACCESS_TAG:
            return Result(False, error="Permanent access does not need renewal")

        days = int(args.days)
        if days <= 0:
            return Result(False, error="Days must be greater than zero")

        if not db.renew_grant(user["uuid"], days):
            return Result(False, error="Failed to renew user in DB")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        updated = db.get_grant_by_uuid(user["uuid"])
        if updated is None:
            return Result(False, error="User was renewed but could not be read back")

        return Result(
            True,
            data={
                **updated,
                "days_added": days,
                **_result_dict(runtime_result),
            },
        )
    except (TypeError, ValueError):
        return Result(False, error="Invalid renewal arguments")
    except Exception:
        logger.exception("Renew failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during renew")


def handle_list(args: Any) -> Result:
    try:
        if getattr(args, "active", False):
            users = db.list_grants("enabled")
        elif getattr(args, "inactive", False):
            users = db.list_grants("disabled")
        else:
            users = db.list_grants()
        return Result(True, data=users)
    except Exception:
        logger.exception("List failed")
        return Result(False, error="Unexpected error during listing")


def handle_delete(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        devices = db.list_devices(user["uuid"])
        if not db.delete_grant_by_uuid(user["uuid"]):
            return Result(False, error="Failed to delete user from DB")

        for device in devices:
            try:
                _remove_device_output(user, device)
            except Exception:
                logger.exception("Failed to remove output for device %s", device["uuid"])

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        return Result(
            True,
            data={
                "deleted_grant_uuid": user["uuid"],
                "deleted_devices": len(devices),
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Delete failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during delete")


def handle_expired(args: Any) -> Result:
    try:
        expired_uuids = db.get_expired_grant_uuids()
        if not expired_uuids:
            return Result(True, data=[])

        disabled = []
        for grant_uuid in expired_uuids:
            if db.set_grant_enabled(grant_uuid, False, "expired"):
                disabled.append(grant_uuid)

        if not disabled:
            return Result(True, data=[])

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        return Result(
            True,
            data={
                "expired_users": disabled,
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Expire job failed")
        return Result(False, error="Unexpected error during expire job")


def handle_device_add(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        device_tag = _device_tag_from_args(args)
        if db.get_device_by_tag(user["uuid"], device_tag):
            return Result(False, error=f"Device already exists: {device_tag}")

        awg_keys = awg.gen_awg_keys()
        awg_ip = awg.get_awg_free_ip(
            AWG_NETWORK,
            db.get_used_ip_addresses(),
        )
        if awg_ip is None:
            return Result(False, error="No free AmneziaWG IP available")

        device_uuid = str(uuid.uuid4())
        created = db.create_device(
            {
                "uuid": device_uuid,
                "access_grant_uuid": user["uuid"],
                "device_tag": device_tag,
                "is_enabled": 1,
                "wg_public_key": awg_keys["public_key"],
                "wg_private_key": awg_keys["private_key"],
                "wg_preshared_key": awg_keys.get("preshared_key"),
                "wg_assigned_ip": awg_ip,
            }
        )
        if created is None:
            return Result(False, error="Failed to create device in DB")

        device = db.get_device_by_uuid(device_uuid)
        if device is None:
            db.delete_device(device_uuid)
            return Result(False, error="Created device could not be read back from DB")

        try:
            config_path = _save_client_config(user, device)
        except Exception:
            logger.exception("Failed to create client config for %s", device_uuid)
            db.delete_device(device_uuid)
            return Result(False, error="Failed to create client configuration")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return Result(
                False,
                data={
                    "device_uuid": device_uuid,
                    "config_path": config_path.as_posix(),
                },
                error=runtime_result.error,
            )

        return Result(
            True,
            data={
                "grant_uuid": user["uuid"],
                "device_uuid": device_uuid,
                "device_tag": device_tag,
                "awg_ip": awg_ip,
                "config_path": config_path.as_posix(),
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Device add failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during device add")


def handle_device_list(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        return Result(True, data=db.list_devices(user["uuid"]))
    except Exception:
        logger.exception("Device list failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during device listing")


def handle_device_disable(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        device_result = _get_device_for_user(args, user)
        if not device_result:
            return device_result

        device = _result_dict(device_result)
        if not device:
            return Result(False, error="Invalid device data")

        if not db.set_device_enabled(device["uuid"], False, "manual"):
            return Result(False, error="Failed to disable device in DB")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        updated = db.get_device_by_uuid(device["uuid"])
        if updated is None:
            return Result(False, error="Device was disabled but could not be read back")

        return Result(
            True,
            data={
                **updated,
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Device disable failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during device disable")


def handle_device_enable(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        if _regular_access_expired(user):
            return Result(False, error="Regular access is expired; renew the user first")

        device_result = _get_device_for_user(args, user)
        if not device_result:
            return device_result

        device = _result_dict(device_result)
        if not device:
            return Result(False, error="Invalid device data")

        if not db.set_device_enabled(device["uuid"], True):
            return Result(False, error="Failed to enable device in DB")

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        updated = db.get_device_by_uuid(device["uuid"])
        if updated is None:
            return Result(False, error="Device was enabled but could not be read back")

        return Result(
            True,
            data={
                **updated,
                **_result_dict(runtime_result),
            },
        )
    except ValueError:
        return Result(False, error="Invalid expiration date in DB")
    except Exception:
        logger.exception("Device enable failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during device enable")


def handle_device_delete(args: Any) -> Result:
    try:
        user_result = get_user_by_telegram(args.telegram)
        if not user_result:
            return user_result

        user = _result_dict(user_result)
        if not user:
            return Result(False, error="Invalid user data")

        device_result = _get_device_for_user(args, user)
        if not device_result:
            return device_result

        device = _result_dict(device_result)
        if not device:
            return Result(False, error="Invalid device data")

        if not db.delete_device(device["uuid"]):
            return Result(False, error="Failed to delete device from DB")

        try:
            _remove_device_output(user, device)
        except Exception:
            logger.exception("Failed to remove output for device %s", device["uuid"])

        runtime_result = rebuild_and_deploy()
        if not runtime_result:
            return runtime_result

        return Result(
            True,
            data={
                "deleted_device_uuid": device["uuid"],
                "device_tag": device["device_tag"],
                **_result_dict(runtime_result),
            },
        )
    except Exception:
        logger.exception("Device delete failed: telegram=%s", getattr(args, "telegram", None))
        return Result(False, error="Unexpected error during device delete")
