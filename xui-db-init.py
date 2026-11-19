import datetime
import os
import sqlite3
from pathlib import Path


data_dir = Path("/etc/x-ui")
db_path = data_dir / "x-ui.db"
marker_path = data_dir / ".vpn-domain-reset-complete"

if not db_path.exists():
    print("X-UI database does not exist yet; skipping one-time reset.")
    raise SystemExit(0)

connection = sqlite3.connect(db_path, timeout=60)
connection.execute("PRAGMA foreign_keys = OFF")
tables = {
    row[0]
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
}

if not {"settings", "users"}.issubset(tables):
    print("X-UI schema is not initialized; skipping one-time reset.")
    connection.close()
    raise SystemExit(0)


def set_setting(key: str, value: str) -> None:
    cursor = connection.execute(
        'UPDATE settings SET value = ? WHERE "key" = ?', (value, key)
    )
    if cursor.rowcount == 0:
        connection.execute(
            'INSERT INTO settings ("key", value) VALUES (?, ?)', (key, value)
        )


perform_reset = not marker_path.exists()
if perform_reset:
    backup_path = data_dir / (
        "x-ui.db.before-reset-"
        + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    backup = sqlite3.connect(backup_path)
    connection.backup(backup)
    backup.close()
    os.chmod(backup_path, 0o600)

    connection.execute("BEGIN IMMEDIATE")
    for table in sorted(tables - {"settings", "users", "sqlite_sequence"}):
        quoted_table = table.replace('"', '""')
        connection.execute(f'DELETE FROM "{quoted_table}"')

set_setting("webDomain", "vpn.bishoy.de")
set_setting("webCertFile", "")
set_setting("webKeyFile", "")
set_setting("trustedProxyCIDRs", "127.0.0.1/32,::1/128,172.16.0.0/12")
connection.commit()
connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
connection.close()
if perform_reset:
    marker_path.write_text("completed\n", encoding="ascii")
print("X-UI data reset, database backed up, and vpn.bishoy.de settings applied.")
