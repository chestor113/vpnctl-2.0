from contextlib import contextmanager
from datetime import datetime, timedelta, UTC
from pathlib import Path
from uuid import uuid4
import logging
import sqlite3


logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "db.sqlite"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
REGULAR_ACCESS_TAG = "regular"


# ----------------------------------------------------------------------
# Common
# ----------------------------------------------------------------------

def _now():
    return datetime.now(UTC)


def _datetime_to_db(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        value = value.astimezone(UTC)

        return value.strftime(
            DATETIME_FORMAT
        )

    return str(value)


def _now_db():
    return _datetime_to_db(
        _now()
    )


def _parse_db_datetime(value):
    if not value:
        return None

    return datetime.strptime(
        value,
        DATETIME_FORMAT,
    ).replace(
        tzinfo=UTC
    )


def _row_to_dict(row):
    if row is None:
        return None

    return dict(row)


def _normalize_access_tag(value):
    tag = str(
        value or REGULAR_ACCESS_TAG
    ).strip()

    if not tag:
        return REGULAR_ACCESS_TAG

    return tag


def _normalize_expiration(
    access_tag,
    expires_at,
):
    """
    Only regular access expires.

    Any non-regular tag means permanent access.
    """

    if access_tag != REGULAR_ACCESS_TAG:
        return None

    return _datetime_to_db(
        expires_at
    )


@contextmanager
def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=5,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    conn.execute(
        "PRAGMA busy_timeout = 5000"
    )

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ======================================================================
# ACCESS GRANTS
# ======================================================================

def get_grant_by_uuid(grant_uuid):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    uuid,
                    username,
                    telegram,
                    created_at,
                    expires_at,
                    is_enabled,
                    turned_off_reason,
                    turned_off_at,
                    access_tag,
                    invited_by_uuid
                FROM access_grants
                WHERE uuid = ?
                """,
                (grant_uuid,),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_grant_by_uuid DB error: %s",
            e,
        )
        return None


def get_grant_by_username(username):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    uuid,
                    username,
                    telegram,
                    created_at,
                    expires_at,
                    is_enabled,
                    turned_off_reason,
                    turned_off_at,
                    access_tag,
                    invited_by_uuid
                FROM access_grants
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_grant_by_username DB error: %s",
            e,
        )
        return None


def get_grant_by_telegram(telegram):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    uuid,
                    username,
                    telegram,
                    created_at,
                    expires_at,
                    is_enabled,
                    turned_off_reason,
                    turned_off_at,
                    access_tag,
                    invited_by_uuid
                FROM access_grants
                WHERE telegram = ?
                """,
                (telegram,),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_grant_by_telegram DB error: %s",
            e,
        )
        return None


def create_grant(payload):
    grant_uuid = (
        payload.get("uuid")
        or str(uuid4())
    )

    access_tag = _normalize_access_tag(
        payload.get("access_tag")
    )

    expires_at = _normalize_expiration(
        access_tag,
        payload.get("expires_at"),
    )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO access_grants (
                    uuid,
                    username,
                    telegram,
                    created_at,
                    expires_at,
                    is_enabled,
                    access_tag,
                    invited_by_uuid
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant_uuid,
                    payload["username"],
                    payload.get("telegram"),
                    _datetime_to_db(
                        payload.get("created_at")
                        or _now()
                    ),
                    expires_at,
                    payload.get(
                        "is_enabled",
                        1,
                    ),
                    access_tag,
                    payload.get(
                        "invited_by_uuid"
                    ),
                ),
            )

            return {
                "id": cursor.lastrowid,
                "uuid": grant_uuid,
            }

    except (
        sqlite3.Error,
        KeyError,
    ) as e:
        logger.error(
            "create_grant error: %s",
            e,
        )
        return None


def set_grant_enabled(
    grant_uuid,
    enabled,
    reason=None,
):
    try:
        with get_connection() as conn:

            if enabled:
                cursor = conn.execute(
                    """
                    UPDATE access_grants
                    SET
                        is_enabled = 1,
                        turned_off_reason = NULL,
                        turned_off_at = NULL
                    WHERE uuid = ?
                    """,
                    (grant_uuid,),
                )

            else:
                cursor = conn.execute(
                    """
                    UPDATE access_grants
                    SET
                        is_enabled = 0,
                        turned_off_reason = ?,
                        turned_off_at = ?
                    WHERE uuid = ?
                    """,
                    (
                        reason,
                        _now_db(),
                        grant_uuid,
                    ),
                )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "set_grant_enabled DB error: %s",
            e,
        )
        return False


def renew_grant(
    grant_uuid,
    days,
):
    """
    Extend regular access.

    Permanent access does not need renewal.

    If regular access is still valid:
        old expires_at + days

    If regular access already expired:
        now + days
    """

    try:
        days = int(days)

        if days <= 0:
            return False

    except (
        TypeError,
        ValueError,
    ):
        return False

    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    access_tag,
                    expires_at
                FROM access_grants
                WHERE uuid = ?
                """,
                (grant_uuid,),
            ).fetchone()

            if row is None:
                return False

            if (
                row["access_tag"]
                != REGULAR_ACCESS_TAG
            ):
                return False

            now = _now()

            try:
                current_expiration = (
                    _parse_db_datetime(
                        row["expires_at"]
                    )
                )

            except ValueError:
                logger.error(
                    "Invalid expires_at for grant %s: %s",
                    grant_uuid,
                    row["expires_at"],
                )
                return False

            if (
                current_expiration
                and current_expiration > now
            ):
                base_date = current_expiration
            else:
                base_date = now

            new_expiration = (
                base_date
                + timedelta(days=days)
            )

            cursor = conn.execute(
                """
                UPDATE access_grants
                SET
                    expires_at = ?,
                    is_enabled = 1,
                    turned_off_reason = NULL,
                    turned_off_at = NULL
                WHERE uuid = ?
                """,
                (
                    _datetime_to_db(
                        new_expiration
                    ),
                    grant_uuid,
                ),
            )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "renew_grant DB error: %s",
            e,
        )
        return False


def list_grants(status=None):
    query = """
        SELECT
            id,
            uuid,
            username,
            telegram,
            created_at,
            expires_at,
            is_enabled,
            turned_off_reason,
            turned_off_at,
            access_tag,
            invited_by_uuid
        FROM access_grants
    """

    if status == "enabled":
        query += """
            WHERE is_enabled = 1
        """

    elif status == "disabled":
        query += """
            WHERE is_enabled = 0
        """

    query += """
        ORDER BY id
    """

    try:
        with get_connection() as conn:
            rows = conn.execute(
                query
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "list_grants DB error: %s",
            e,
        )
        return []


def get_expired_grant_uuids():
    """
    Only regular users can expire.
    """

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT uuid
                FROM access_grants
                WHERE
                    is_enabled = 1
                    AND access_tag = ?
                    AND expires_at IS NOT NULL
                    AND expires_at <= ?
                """,
                (
                    REGULAR_ACCESS_TAG,
                    _now_db(),
                ),
            ).fetchall()

            return [
                row["uuid"]
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "get_expired_grant_uuids DB error: %s",
            e,
        )
        return []


def get_effective_active_grant_uuids():
    """
    Effective VPN access:

    regular:
        enabled + expires_at > now

    anything except regular:
        enabled
    """

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT uuid
                FROM access_grants
                WHERE
                    is_enabled = 1
                    AND (
                        access_tag != ?
                        OR (
                            access_tag = ?
                            AND expires_at IS NOT NULL
                            AND expires_at > ?
                        )
                    )
                """,
                (
                    REGULAR_ACCESS_TAG,
                    REGULAR_ACCESS_TAG,
                    _now_db(),
                ),
            ).fetchall()

            return [
                row["uuid"]
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "get_effective_active_grant_uuids DB error: %s",
            e,
        )
        return []


def delete_grant_by_uuid(
    grant_uuid,
):
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM access_grants
                WHERE uuid = ?
                """,
                (grant_uuid,),
            )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "delete_grant_by_uuid DB error: %s",
            e,
        )
        return False


def delete_grant_by_telegram(
    telegram,
):
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM access_grants
                WHERE telegram = ?
                """,
                (telegram,),
            )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "delete_grant_by_telegram DB error: %s",
            e,
        )
        return False


# ======================================================================
# DEVICES
# ======================================================================

def create_device(payload):
    device_uuid = (
        payload.get("uuid")
        or str(uuid4())
    )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO devices (
                    uuid,
                    access_grant_uuid,
                    device_tag,
                    created_at,
                    is_enabled,
                    wg_public_key,
                    wg_private_key,
                    wg_assigned_ip,
                    wg_preshared_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_uuid,
                    payload[
                        "access_grant_uuid"
                    ],
                    payload.get(
                        "device_tag"
                    ) or "phone",
                    _datetime_to_db(
                        payload.get(
                            "created_at"
                        )
                        or _now()
                    ),
                    payload.get(
                        "is_enabled",
                        1,
                    ),
                    payload[
                        "wg_public_key"
                    ],
                    payload[
                        "wg_private_key"
                    ],
                    payload[
                        "wg_assigned_ip"
                    ],
                    payload.get(
                        "wg_preshared_key"
                    ),
                ),
            )

            return {
                "id": cursor.lastrowid,
                "uuid": device_uuid,
            }

    except (
        sqlite3.Error,
        KeyError,
    ) as e:
        logger.error(
            "create_device error: %s",
            e,
        )
        return None


def get_device_by_uuid(
    device_uuid,
):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM devices
                WHERE uuid = ?
                """,
                (device_uuid,),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_device_by_uuid DB error: %s",
            e,
        )
        return None


def get_device_by_tag(
    grant_uuid,
    device_tag,
):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM devices
                WHERE
                    access_grant_uuid = ?
                    AND device_tag = ?
                ORDER BY id
                LIMIT 1
                """,
                (
                    grant_uuid,
                    device_tag,
                ),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_device_by_tag DB error: %s",
            e,
        )
        return None


def list_devices(grant_uuid):
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    uuid,
                    access_grant_uuid,
                    device_tag,
                    created_at,
                    is_enabled,
                    turned_off_reason,
                    turned_off_at,
                    wg_public_key,
                    wg_private_key,
                    wg_assigned_ip,
                    wg_preshared_key
                FROM devices
                WHERE access_grant_uuid = ?
                ORDER BY id
                """,
                (grant_uuid,),
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "list_devices DB error: %s",
            e,
        )
        return []


def list_all_devices():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    uuid,
                    access_grant_uuid,
                    device_tag,
                    created_at,
                    is_enabled,
                    turned_off_reason,
                    turned_off_at,
                    wg_public_key,
                    wg_assigned_ip
                FROM devices
                ORDER BY id
                """
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "list_all_devices DB error: %s",
            e,
        )
        return []


def set_device_enabled(
    device_uuid,
    enabled,
    reason=None,
):
    try:
        with get_connection() as conn:

            if enabled:
                cursor = conn.execute(
                    """
                    UPDATE devices
                    SET
                        is_enabled = 1,
                        turned_off_reason = NULL,
                        turned_off_at = NULL
                    WHERE uuid = ?
                    """,
                    (device_uuid,),
                )

            else:
                cursor = conn.execute(
                    """
                    UPDATE devices
                    SET
                        is_enabled = 0,
                        turned_off_reason = ?,
                        turned_off_at = ?
                    WHERE uuid = ?
                    """,
                    (
                        reason,
                        _now_db(),
                        device_uuid,
                    ),
                )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "set_device_enabled DB error: %s",
            e,
        )
        return False


def delete_device(
    device_uuid,
):
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM devices
                WHERE uuid = ?
                """,
                (device_uuid,),
            )

            return cursor.rowcount == 1

    except sqlite3.Error as e:
        logger.error(
            "delete_device DB error: %s",
            e,
        )
        return False


def get_used_ip_addresses():
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT wg_assigned_ip
                FROM devices
                WHERE wg_assigned_ip IS NOT NULL
                ORDER BY id
                """
            ).fetchall()

            return [
                row["wg_assigned_ip"]
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "get_used_ip_addresses DB error: %s",
            e,
        )
        return []


# ======================================================================
# CREATE USER + FIRST DEVICE
# ======================================================================

def create_grant_with_first_device(
    grant_payload,
    device_payload,
):
    """
    Create grant and first device
    in one transaction.
    """

    grant_uuid = (
        grant_payload.get("uuid")
        or str(uuid4())
    )

    device_uuid = (
        device_payload.get("uuid")
        or str(uuid4())
    )

    created_at = _datetime_to_db(
        grant_payload.get(
            "created_at"
        )
        or _now()
    )

    access_tag = _normalize_access_tag(
        grant_payload.get(
            "access_tag"
        )
    )

    expires_at = _normalize_expiration(
        access_tag,
        grant_payload.get(
            "expires_at"
        ),
    )

    try:
        with get_connection() as conn:

            grant_cursor = conn.execute(
                """
                INSERT INTO access_grants (
                    uuid,
                    username,
                    telegram,
                    created_at,
                    expires_at,
                    is_enabled,
                    access_tag,
                    invited_by_uuid
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant_uuid,
                    grant_payload[
                        "username"
                    ],
                    grant_payload.get(
                        "telegram"
                    ),
                    created_at,
                    expires_at,
                    grant_payload.get(
                        "is_enabled",
                        1,
                    ),
                    access_tag,
                    grant_payload.get(
                        "invited_by_uuid"
                    ),
                ),
            )

            device_cursor = conn.execute(
                """
                INSERT INTO devices (
                    uuid,
                    access_grant_uuid,
                    device_tag,
                    created_at,
                    is_enabled,
                    wg_public_key,
                    wg_private_key,
                    wg_assigned_ip,
                    wg_preshared_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_uuid,
                    grant_uuid,
                    device_payload.get(
                        "device_tag"
                    ) or "phone",
                    _datetime_to_db(
                        device_payload.get(
                            "created_at"
                        )
                        or created_at
                    ),
                    device_payload.get(
                        "is_enabled",
                        1,
                    ),
                    device_payload[
                        "wg_public_key"
                    ],
                    device_payload[
                        "wg_private_key"
                    ],
                    device_payload[
                        "wg_assigned_ip"
                    ],
                    device_payload.get(
                        "wg_preshared_key"
                    ),
                ),
            )

            return {
                "grant_id":
                    grant_cursor.lastrowid,
                "grant_uuid":
                    grant_uuid,
                "device_id":
                    device_cursor.lastrowid,
                "device_uuid":
                    device_uuid,
            }

    except (
        sqlite3.Error,
        KeyError,
    ) as e:
        logger.error(
            "create_grant_with_first_device error: %s",
            e,
        )
        return None


# ======================================================================
# AWG RUNTIME
# ======================================================================

def get_active_awg_peers():
    """
    Return peers which should currently
    exist in awg0.conf.

    regular:
        user enabled
        device enabled
        expires_at > now

    non-regular:
        user enabled
        device enabled
        expiration ignored
    """

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.uuid AS device_uuid,
                    d.device_tag,
                    d.wg_public_key,
                    d.wg_preshared_key,
                    d.wg_assigned_ip,

                    a.uuid AS grant_uuid,
                    a.username,
                    a.telegram,
                    a.access_tag,
                    a.expires_at

                FROM devices AS d

                JOIN access_grants AS a
                    ON a.uuid = d.access_grant_uuid

                WHERE
                    d.is_enabled = 1
                    AND a.is_enabled = 1
                    AND (
                        a.access_tag != ?
                        OR (
                            a.access_tag = ?
                            AND a.expires_at IS NOT NULL
                            AND a.expires_at > ?
                        )
                    )

                ORDER BY
                    a.username,
                    d.id
                """,
                (
                    REGULAR_ACCESS_TAG,
                    REGULAR_ACCESS_TAG,
                    _now_db(),
                ),
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(
            "get_active_awg_peers DB error: %s",
            e,
        )
        return []


def get_device_config_data(
    device_uuid,
):
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    d.uuid AS device_uuid,
                    d.device_tag,
                    d.created_at AS device_created_at,
                    d.is_enabled AS device_enabled,

                    d.wg_public_key,
                    d.wg_private_key,
                    d.wg_preshared_key,
                    d.wg_assigned_ip,

                    a.uuid AS grant_uuid,
                    a.username,
                    a.telegram,
                    a.access_tag,
                    a.expires_at,
                    a.is_enabled AS grant_enabled

                FROM devices AS d

                JOIN access_grants AS a
                    ON a.uuid = d.access_grant_uuid

                WHERE d.uuid = ?
                """,
                (device_uuid,),
            ).fetchone()

            return _row_to_dict(row)

    except sqlite3.Error as e:
        logger.error(
            "get_device_config_data DB error: %s",
            e,
        )
        return None


def get_grant_with_devices(
    grant_uuid,
):
    grant = get_grant_by_uuid(
        grant_uuid
    )

    if grant is None:
        return None

    grant["devices"] = list_devices(
        grant_uuid
    )

    return grant


# ======================================================================
# TEMPORARY COMPATIBILITY WITH OLD CODE
# ======================================================================

def find_by_uuid(uuid):
    return get_grant_by_uuid(
        uuid
    )


def find_by_username(username):
    return get_grant_by_username(
        username
    )


def find_by_telegram(telegram):
    return get_grant_by_telegram(
        telegram
    )


def insert_grant(payload):
    """
    Compatibility with old services.py.
    """

    has_device_data = (
        payload.get("wg_public_key")
        and payload.get("wg_private_key")
        and payload.get("wg_assigned_ip")
    )

    if not has_device_data:
        result = create_grant(
            payload
        )

        if result is None:
            return None

        return result["id"]

    device_payload = {
        "device_tag":
            payload.get("device_tag")
            or "phone",

        "wg_public_key":
            payload["wg_public_key"],

        "wg_private_key":
            payload["wg_private_key"],

        "wg_assigned_ip":
            payload["wg_assigned_ip"],

        "wg_preshared_key":
            payload.get(
                "wg_preshared_key"
            ),
    }

    result = (
        create_grant_with_first_device(
            grant_payload=payload,
            device_payload=device_payload,
        )
    )

    if result is None:
        return None

    return result["grant_id"]


def enable_by_uuid(uuid):
    return set_grant_enabled(
        uuid,
        True,
    )


def disable_by_uuid(
    uuid,
    reason,
):
    return set_grant_enabled(
        uuid,
        False,
        reason,
    )


def renew_by_uuid(
    uuid,
    days,
):
    return renew_grant(
        uuid,
        days,
    )


def get_all_clients():
    return list_grants()


def get_all_active_clients():
    return list_grants(
        "enabled"
    )


def get_uuid_active_clients():
    return (
        get_effective_active_grant_uuids()
    )


def get_inactive_clients():
    return list_grants(
        "disabled"
    )


def get_expired_uuids():
    return (
        get_expired_grant_uuids()
    )


def expire_job():
    expired = (
        get_expired_grant_uuids()
    )

    if not expired:
        return None

    for grant_uuid in expired:
        if set_grant_enabled(
            grant_uuid,
            False,
            "expired",
        ):
            logger.info(
                "Expire user: %s",
                grant_uuid,
            )

    return expired


def get_ip_addresses():
    return get_used_ip_addresses()


def delete_user(telegram):
    return (
        delete_grant_by_telegram(
            telegram
        )
    )