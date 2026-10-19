# vpnctl

Небольшой CLI для управления доступом к AmneziaWG VPN.

Используется SQLite. Один пользователь может иметь несколько устройств, у каждого устройства свои ключи и VPN IP.

## Основные команды

Создать пользователя:

```bash
python3 vpnctl.py create -u ivan -t ivan_tg -d 180
```

Где:

```text
-u  имя пользователя
-t  Telegram
-d  срок доступа в днях
```

Если устройство не указано, по умолчанию создаётся:

```text
phone
```

Продлить доступ:

```bash
python3 vpnctl.py renew -t ivan_tg -d 30
```

Отключить пользователя:

```bash
python3 vpnctl.py disable -t ivan_tg
```

Включить пользователя:

```bash
python3 vpnctl.py enable -t ivan_tg
```

Показать пользователей:

```bash
python3 vpnctl.py list --all
```

Удалить пользователя:

```bash
python3 vpnctl.py delete -t ivan_tg
```

## Устройства

У одного пользователя может быть несколько устройств:

```text
ivan
├── phone
├── laptop
└── desktop
```

Добавление нового устройства:

```bash
python3 vpnctl.py device-add -t ivan_tg --device laptop
```

Каждое устройство получает отдельные:

```text
private key
public key
preshared key
VPN IP
```

## База

Используется SQLite.

Схема новой базы:

```text
db/schema.sql
```

Рабочая база:

```text
db.sqlite
```

Таблицы:

```text
access_grants
devices
```

Проверить:

```bash
sqlite3 db.sqlite ".tables"
```

## Развёртывание

Приложение разворачивается Ansible в:

```text
/opt/vpnctl
```

Ansible ставит зависимости, забирает код и при первой установке создаёт SQLite-базу.
