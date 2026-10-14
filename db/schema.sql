CREATE TABLE IF NOT EXISTS access_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    telegram TEXT UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    turned_off_reason TEXT,
    turned_off_at TEXT,
    access_tag TEXT NOT NULL DEFAULT 'regular',
    invited_by_uuid TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    access_grant_uuid TEXT NOT NULL,

    device_tag TEXT NOT NULL DEFAULT 'phone',

    created_at TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    turned_off_reason TEXT,
    turned_off_at TEXT,

    wg_public_key TEXT NOT NULL UNIQUE,
    wg_private_key TEXT NOT NULL,
    wg_assigned_ip TEXT NOT NULL UNIQUE,
    wg_preshared_key TEXT,

    FOREIGN KEY (access_grant_uuid)
        REFERENCES access_grants(uuid)
        ON DELETE CASCADE
);
