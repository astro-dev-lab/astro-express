"""Versioned SQL migrations, advisory transaction lock, no automatic startup mutation."""
import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit
import psycopg
from .config import validate_database_url

ROOT = Path(__file__).resolve().parent / "migrations"
LOCK_ID = 726081341


def migrate(database_url, direction="up", confirm=None):
    validate_database_url(database_url)
    if direction not in {"up", "down"}:
        raise ValueError("Unknown migration direction")
    database = urlsplit(database_url).path.lstrip("/")
    if direction == "down" and (not database.startswith("astro_test_") or confirm != database):
        raise ValueError("Downgrade requires disposable astro_test_ database and exact name confirmation")
    with psycopg.connect(database_url, hostaddr="::1" if urlsplit(database_url).hostname == "::1" else "127.0.0.1", connect_timeout=3, options="-c statement_timeout=10000") as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        if any(version != 1 for version in versions):
            raise ValueError("Unknown migration version; no changes applied")
        if direction == "up" and 1 not in versions:
            conn.execute((ROOT / "001_foundation.up.sql").read_text())
            conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (1,))
        elif direction == "down" and 1 in versions:
            conn.execute((ROOT / "001_foundation.down.sql").read_text())
            conn.execute("DELETE FROM schema_migrations WHERE version=%s", (1,))


def main():
    parser = argparse.ArgumentParser(description="Apply local PostgreSQL migrations explicitly")
    parser.add_argument("direction", choices=["up", "down"])
    parser.add_argument("--confirm-disposable-database")
    args = parser.parse_args()
    try:
        migrate(os.environ.get("DATABASE_URL", ""), args.direction, args.confirm_disposable_database)
    except Exception:
        parser.exit(1, "Migration failed; database configuration, availability or migration state must be checked locally.\n")
    print("Migration completed")


if __name__ == "__main__":
    main()
