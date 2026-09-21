"""Lightweight, idempotent migration system.

Each migration is a function ``f(conn)`` that performs idempotent DDL
(``IF NOT EXISTS`` for tables/indexes, guarded ``ADD COLUMN`` /
``RENAME COLUMN``). The runner:

- records progress in a ``schema_version`` table
- runs each pending migration inside a transaction
- copies the DB file to ``data/backups/`` before touching anything, so a
  failed migration never silently corrupts data
- re-raises on failure (never hides it)

New install  → runs all migrations from version 0 → final schema.
Legacy v1 DB → table already exists; m001 is a no-op, m002 extends in place.
"""

from __future__ import annotations

import logging
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import settings
from .errors import ErrorCode, SiteUnitError

log = logging.getLogger("siteunit.migrations")

Migration = Callable[[sqlite3.Connection], None]


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn, table: str, col: str, definition: str) -> None:
    if col in _columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


def _rename_column(conn, table: str, old: str, new: str) -> None:
    if old in _columns(conn, table) and new not in _columns(conn, table):
        conn.execute(f'ALTER TABLE {table} RENAME COLUMN "{old}" TO "{new}"')


def _create_index(conn, name: str, body: str) -> None:
    conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {body}")


# ---------- migration 001: original baseline schema ----------

def m001_baseline(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            grp         TEXT NOT NULL DEFAULT '',
            logo        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
        """
    )


# ---------- migration 002: extend to the full data model ----------

def m002_extend(conn: sqlite3.Connection) -> None:
    # Rename legacy columns to clean names (no-op if already renamed).
    _rename_column(conn, "sites", "grp", "group_name")
    _rename_column(conn, "sites", "logo", "logo_path")

    for col, definition in (
        ("normalized_url", "TEXT NOT NULL DEFAULT ''"),
        ("logo_source", "TEXT NOT NULL DEFAULT ''"),
        ("favorite", "INTEGER NOT NULL DEFAULT 0"),
        ("pinned", "INTEGER NOT NULL DEFAULT 0"),
        ("sort_order", "INTEGER NOT NULL DEFAULT 0"),
        ("last_visited_at", "TEXT"),
        ("visit_count", "INTEGER NOT NULL DEFAULT 0"),
        ("last_checked_at", "TEXT"),
        ("status", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("http_status", "INTEGER"),
        ("archived", "INTEGER NOT NULL DEFAULT 0"),
    ):
        _add_column(conn, "sites", col, definition)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS site_tags (
            site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (site_id, tag_id)
        )
        """
    )

    for name, body in (
        ("idx_sites_normalized", "sites(normalized_url)"),
        ("idx_sites_group", "sites(group_name)"),
        ("idx_sites_sort", "sites(sort_order)"),
        ("idx_sites_archived", "sites(archived)"),
        ("idx_sites_status", "sites(status)"),
        ("idx_sites_pinned", "sites(pinned)"),
        ("idx_sitetags_tag", "site_tags(tag_id)"),
    ):
        _create_index(conn, name, body)


def m003_visit_events(conn: sqlite3.Connection) -> None:
    """Store one append-only row per visit for statistics."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visit_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id    INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            visited_at TEXT NOT NULL
        )
        """
    )
    for name, body in (
        ("idx_visit_events_visited_at", "visit_events(visited_at)"),
        ("idx_visit_events_site_visited_at", "visit_events(site_id, visited_at)"),
    ):
        _create_index(conn, name, body)


MIGRATIONS: list[tuple[int, Migration]] = [
    (1, m001_baseline),
    (2, m002_extend),
    (3, m003_visit_events),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()
    return int(row[0]) if row else 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("INSERT OR REPLACE INTO schema_version(version) VALUES (?)", (version,))


def _backup(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = settings.backup_dir / f"pre-migrate-{stamp}.db"
    try:
        shutil.copy2(db_path, dest)
        log.info("backed up db to %s before migration", dest)
        return dest
    except OSError as e:
        log.warning("could not back up db before migration: %s", e)
        return None


def run_migrations(db_path: Path) -> int:
    """Run all pending migrations. Returns the resulting schema version."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        current = _current_version(conn)
        pending = [(v, fn) for v, fn in MIGRATIONS if v > current]
        if not pending:
            return current
        _backup(db_path)
        for version, fn in pending:
            try:
                conn.execute("BEGIN")
                fn(conn)
                _set_version(conn, version)
                conn.execute("COMMIT")
                log.info("migration %s applied", version)
            except Exception as e:  # noqa: BLE001
                conn.execute("ROLLBACK")
                log.exception("migration %s failed", version)
                raise SiteUnitError(
                    ErrorCode.INTERNAL_ERROR,
                    f"数据库迁移 {version} 失败：{e}（已自动回滚，旧数据未损坏；备份见 data/backups/）",
                    status_code=500,
                ) from e
        return LATEST_VERSION
    finally:
        conn.close()
