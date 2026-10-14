from datetime import datetime, timedelta, UTC
import logging
import sqlite3

logger = logging.getLogger(__name__)

# поиск по uuid
def find_by_uuid(uuid):
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = cursor.execute("""select uuid, username, telegram, created_at, expires_at, is_enabled, access_tag from access_grants where uuid=?""", (uuid,)).fetchone()
        if not row:
            return None
        return dict(row)
    
def find_by_username(username):
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = cursor.execute("select * from access_grants where username=?", (username,)).fetchone()
        if not row:
            return None
        return dict(row)
    
def find_by_telegram(telegram):
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = cursor.execute("select * from access_grants where telegram=?", (telegram,)).fetchone()
        if not row:
            return None
        return dict(row)

# вставка нового пользователя
def insert_grant(payload):
    with sqlite3.connect("db.sqlite") as conn:
        try:
            cursor = conn.execute("""
        INSERT INTO access_grants (
            uuid, username, telegram, created_at, expires_at, is_enabled, access_tag, wg_public_key, wg_private_key, wg_assigned_ip, wg_preshared_key
        ) VALUES (
            :uuid, :username, :telegram, :created_at, :expires_at, :is_enabled, :access_tag, :wg_public_key, :wg_private_key, :wg_assigned_ip, :wg_preshared_key
        )
        """, payload)
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return None
    
def enable_by_uuid(uuid):
    with sqlite3.connect("db.sqlite") as conn:
        try:
            cursor = conn.execute("""update access_grants set is_enabled=1, turned_off_reason=null, turned_off_at=null where uuid = ? """, (uuid,))
            if cursor.rowcount == 1:
                return True
            else: return False
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return False

def disable_by_uuid(uuid, reason):
    with sqlite3.connect("db.sqlite") as conn:
        now = datetime.now(UTC)
        try:
            cursor = conn.execute("""update access_grants set is_enabled=0 , turned_off_reason=?, turned_off_at=? where uuid = ? """, (reason,now.strftime("%Y-%m-%d %H:%M:%S"), uuid))
            if cursor.rowcount == 1:
                return True
            else: return False
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return False

def renew_by_uuid(uuid, days):
    with sqlite3.connect("db.sqlite") as conn:
        try:
            now = datetime.now(UTC)
            new_exp_date = now + timedelta(days = days)
            cursor = conn.execute("""update access_grants set expires_at=? , turned_off_reason=null, turned_off_at=null, is_enabled=1 where uuid = ? """, (new_exp_date.strftime("%Y-%m-%d %H:%M:%S"),uuid))
            if cursor.rowcount == 1:
                return True
            else: return False
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return False
        

def get_all_clients():
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(UTC)
            rows = conn.execute(
                """select id, uuid, username, telegram, is_enabled, created_at, expires_at, access_tag, turned_off_reason, turned_off_at from access_grants"""
            ).fetchall()
            if not rows:
                return []
            return [dict(row) for row in rows]
        
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []
        

def get_all_active_clients():
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(UTC)
            rows = conn.execute(
                """select uuid, username, telegram, access_tag, expires_at from access_grants where is_enabled = 1"""
            ).fetchall()
            if not rows:
                return []
            return [dict(row) for row in rows]
        
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []

def get_uuid_active_clients():
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(UTC)
            rows = conn.execute(
                """select uuid from access_grants where (access_tag='vip' and is_enabled=1) or (is_enabled = 1 and expires_at > ?);""", (now.strftime("%Y-%m-%d %H:%M:%S"),)
            ).fetchall()
            if not rows:
                return []
            return [row['uuid'] for row in rows]
        
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []
        
def get_inactive_clients():
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(UTC)
            rows = conn.execute(
                """select uuid, username, telegram, expires_at, turned_off_reason, turned_off_at, is_enabled  from access_grants where is_enabled = 0;"""
            ).fetchall()
            if not rows:
                return []
            return [dict(row) for row in rows]
        
        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []
        
def get_expired_uuids():
    with sqlite3.connect("db.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        try:
            now = datetime.now(UTC)

            rows = conn.execute(
                """select uuid from access_grants where  (expires_at < ? and is_enabled = 1) and access_tag != 'vip';""",
                 (now.strftime("%Y-%m-%d %H:%M:%S"),)
            ).fetchall()

            return [row[0] for row in rows]

        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []

def expire_job():  
    off_result = get_expired_uuids()
    if off_result:
        for uuid in off_result:
            disable_by_uuid(uuid, 'expired')
            logger.info("Expire user: %s ", uuid)
        return off_result
    else: return None

def get_ip_addresses():
    with sqlite3.connect("db.sqlite") as conn:
        try:
            cursor = conn.execute(
                """select wg_assigned_ip from access_grants ; """).fetchall()

            return [row[0] for row in cursor if row[0] is not None]

        except sqlite3.Error as e:
            logger.info("Error: %s", e)
            return []
        
def delete_user(telegram):
    with sqlite3.connect("db.sqlite") as conn:
        try:
            cursor = conn.execute(
                "DELETE FROM access_grants WHERE telegram=?",
                (telegram,)
            )

            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error("DB error: %s", e)
            return False