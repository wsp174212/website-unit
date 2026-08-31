"""SQLite access layer for the site registry."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "sites.db"
LOGO_DIR = DATA_DIR / "logos"

SITE_COLUMNS = (
    "id",
    "name",
    "url",
    "description",
    "grp",
    "logo",
    "created_at",
    "updated_at",
)


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with _connect() as conn:
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


def list_sites() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sites ORDER BY grp, created_at, id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_site(site_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sites WHERE id = ?", (site_id,)
        ).fetchone()
    return dict(row) if row else None


def insert_site(name: str, url: str, description: str, grp: str, logo: str) -> dict:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sites (name, url, description, grp, logo, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, url, description, grp, logo, now, now),
        )
        new_id = cur.lastrowid
    return get_site(new_id)


def update_site(site_id: int, fields: dict) -> dict | None:
    allowed = {k: v for k, v in fields.items() if k in ("name", "url", "description", "grp", "logo")}
    if not allowed:
        return get_site(site_id)
    allowed["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [site_id]
    with _connect() as conn:
        conn.execute(f"UPDATE sites SET {assignments} WHERE id = ?", values)
    return get_site(site_id)


def delete_site(site_id: int) -> str | None:
    """Delete a site and return its logo filename (if any) so the caller can clean up."""
    site = get_site(site_id)
    if site is None:
        return None
    with _connect() as conn:
        conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
    return site["logo"] or None
