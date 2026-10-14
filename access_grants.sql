-- access_grants определение

CREATE TABLE access_grants(
    id integer primary key autoincrement,
    uuid text not null unique,
    username text not null,
    telegram text UNIQUE,
    created_at text not null,
    expires_at text,
    is_enabled integer not null default 1,
    turned_off_reason text,
    turned_off_at text,
    access_tag text not null default 'regular',
    invited_by_uuid text,
    wg_public_key TEXT NOT NULL UNIQUE,
    wg_private_key TEXT,
    wg_assigned_ip TEXT NOT NULL UNIQUE,
    wg_preshared_key TEXT
);