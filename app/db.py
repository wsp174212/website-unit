"""SQLite data access layer (final schema, post-migration 003).

Connection policy:
- a fresh connection per operation (writes are short, single-user load)
- WAL journal mode for better read/write concurrency
- busy_timeout to tolerate brief lock contention
- foreign_keys ON so site/tag deletes cascade

The data directory is read from ``config.settings`` at call time, so tests
can redirect it via ``config.configure(data_dir=...)``.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .config import settings
from .logos import logo_url_for
from .migrations import run_migrations
from .urlnorm import normalize_url, canonical_key

log = logging.getLogger("siteunit.db")

# Columns that may be updated by the user (update_site whitelist).
EDITABLE_COLUMNS = {
    "name", "url", "normalized_url", "description", "group_name",
    "logo_path", "logo_source", "favorite", "pinned", "sort_order", "archived",
}

ORDER_BY = {
    "custom": "pinned DESC, group_name ASC, sort_order ASC, created_at ASC, id ASC",
    "recent": "pinned DESC, CASE WHEN last_visited_at IS NULL THEN 1 ELSE 0 END, last_visited_at DESC",
    "most": "pinned DESC, visit_count DESC, last_visited_at DESC",
    "added": "pinned DESC, created_at DESC",
    "name": "pinned DESC, name COLLATE NOCASE ASC",
}


@contextmanager
def _connect() -> sqlite3.Connection:
    """A connection that commits on success, rolls back on error, and
    always closes — important on Windows where an open handle locks the file
    and blocks backup/restore from replacing it."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    version = run_migrations(settings.db_path)
    # Backfill normalized_url for any rows lacking it (legacy or skipped).
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, url FROM sites WHERE normalized_url IS NULL OR normalized_url = ''"
        ).fetchall()
        for row in rows:
            try:
                key = canonical_key(row["url"])
            except Exception:
                key = row["url"]
            conn.execute(
                "UPDATE sites SET normalized_url = ? WHERE id = ?",
                (key, row["id"]),
            )
    log.info("database ready (schema v%s, %d sites backfilled)", version, len(rows) if rows else 0)


# ---------- queries ----------

def _attach_tags(conn: sqlite3.Connection, site_ids: list[int]) -> dict[int, list[str]]:
    if not site_ids:
        return {}
    placeholders = ",".join("?" * len(site_ids))
    rows = conn.execute(
        f"""
        SELECT st.site_id AS sid, t.name
        FROM site_tags st JOIN tags t ON t.id = st.tag_id
        WHERE st.site_id IN ({placeholders})
        ORDER BY t.name COLLATE NOCASE
        """,
        site_ids,
    ).fetchall()
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r["sid"], []).append(r["name"])
    return out


def _row_to_site(row: sqlite3.Row, tags: list[str] | None = None) -> dict:
    d = dict(row)
    d["tags"] = tags if tags is not None else []
    return d


def list_sites(
    *,
    order: str = "custom",
    archived: bool | None = False,
    text: str | None = None,
    group: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    pinned: bool | None = None,
) -> list[dict]:
    order_clause = ORDER_BY.get(order, ORDER_BY["custom"])
    where: list[str] = []
    params: list = []

    if archived is not None:
        where.append("archived = ?")
        params.append(1 if archived else 0)
    if group is not None:
        where.append("group_name = ?")
        params.append(group)
    if tag is not None:
        where.append("id IN (SELECT site_id FROM site_tags st JOIN tags t ON t.id=st.tag_id WHERE t.name = ? COLLATE NOCASE)")
        params.append(tag)
    if favorite:
        where.append("favorite = 1")
    if pinned:
        where.append("pinned = 1")
    if text:
        q = f"%{text.lower()}%"
        where.append(
            "(lower(name) LIKE ? OR lower(url) LIKE ? OR lower(description) LIKE ? "
            "OR lower(group_name) LIKE ? OR id IN ("
            "SELECT site_id FROM site_tags st JOIN tags t ON t.id=st.tag_id WHERE lower(t.name) LIKE ?))"
        )
        params.extend([q, q, q, q, q])

    sql = "SELECT * FROM sites"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_clause}"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        tags_map = _attach_tags(conn, [r["id"] for r in rows])
    return [_row_to_site(r, tags_map.get(r["id"], [])) for r in rows]


def get_site(site_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        if not row:
            return None
        tags = _attach_tags(conn, [site_id]).get(site_id, [])
    return _row_to_site(row, tags)


def get_by_normalized_url(url: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sites WHERE normalized_url = ?", (canonical_key(url),)
        ).fetchone()
        if not row:
            return None
        tags = _attach_tags(conn, [row["id"]]).get(row["id"], [])
    return _row_to_site(row, tags)


# ---------- mutations ----------

def insert_site(*, name: str, url: str, description: str, group_name: str,
                logo_path: str, logo_source: str, tags: list[str] | None = None) -> dict:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO sites
               (name, url, normalized_url, description, group_name, logo_path, logo_source,
                favorite, pinned, sort_order, created_at, updated_at, visit_count, status, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, 0, 'unknown', 0)""",
            (name, url, canonical_key(url), description, group_name, logo_path, logo_source, now, now),
        )
        new_id = cur.lastrowid
        if tags:
            _set_tags(conn, new_id, tags)
    return get_site(new_id)


def update_site(site_id: int, fields: dict) -> dict | None:
    if get_site(site_id) is None:
        return None
    allowed = {k: v for k, v in fields.items() if k in EDITABLE_COLUMNS}
    tags = fields.get("tags")
    if "url" in allowed and allowed["url"]:
        allowed["normalized_url"] = canonical_key(allowed["url"])
    allowed["updated_at"] = _now()
    with _connect() as conn:
        if allowed:
            assignments = ", ".join(f'"{k}" = ?' for k in allowed)
            conn.execute(f"UPDATE sites SET {assignments} WHERE id = ?",
                         list(allowed.values()) + [site_id])
        if tags is not None:
            _set_tags(conn, site_id, tags)
    return get_site(site_id)


def delete_site(site_id: int) -> dict | None:
    """Delete a site; return the deleted row (so the caller can clean up its
    logo) or None if it did not exist."""
    site = get_site(site_id)
    if site is None:
        return None
    with _connect() as conn:
        conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
    return site


def record_visit_event(
    conn: sqlite3.Connection, site_id: int, visited_at: str
) -> None:
    """Append one visit event inside the caller's transaction."""
    conn.execute(
        "INSERT INTO visit_events (site_id, visited_at) VALUES (?, ?)",
        (site_id, visited_at),
    )


def visit_site(site_id: int) -> bool:
    """Increment visit_count, bump last_visited_at, and append an event."""
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE sites SET visit_count = visit_count + 1, last_visited_at = ? WHERE id = ?",
            (now, site_id),
        )
        if cur.rowcount:
            record_visit_event(conn, site_id, now)
        return cur.rowcount > 0


def stats_overview(days: int) -> dict:
    """Aggregate visits for the last ``days`` UTC calendar days."""
    now = _now()
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    daily = {date.isoformat(): 0 for date in dates}
    end_date = today + timedelta(days=1)

    with _connect() as conn:
        daily_rows = conn.execute(
            """
            SELECT substr(ve.visited_at, 1, 10) AS date, COUNT(*) AS count
            FROM visit_events ve
            JOIN sites s ON s.id = ve.site_id
            WHERE s.archived = 0
              AND ve.visited_at >= ?
              AND ve.visited_at < ?
              AND ve.visited_at <= ?
            GROUP BY date
            """,
            (start_date.isoformat(), end_date.isoformat(), now),
        ).fetchall()
        for row in daily_rows:
            daily[row["date"]] = row["count"]

        top_rows = conn.execute(
            """
            SELECT s.id AS site_id, s.name, s.url, s.logo_path, COUNT(*) AS visits
            FROM visit_events ve
            JOIN sites s ON s.id = ve.site_id
            WHERE s.archived = 0
              AND ve.visited_at >= ?
              AND ve.visited_at < ?
              AND ve.visited_at <= ?
            GROUP BY s.id, s.name, s.url, s.logo_path
            ORDER BY visits DESC, s.id ASC
            LIMIT 10
            """,
            (start_date.isoformat(), end_date.isoformat(), now),
        ).fetchall()

        group_rows = conn.execute(
            """
            SELECT s.group_name AS name, COUNT(*) AS count
            FROM visit_events ve
            JOIN sites s ON s.id = ve.site_id
            WHERE s.archived = 0
              AND ve.visited_at >= ?
              AND ve.visited_at < ?
              AND ve.visited_at <= ?
            GROUP BY s.group_name
            """,
            (start_date.isoformat(), end_date.isoformat(), now),
        ).fetchall()

    groups = [
        {"name": row["name"], "count": row["count"]}
        for row in sorted(
            group_rows,
            key=lambda row: (-row["count"], row["name"] == "", row["name"].lower()),
        )
    ]
    return {
        "days": days,
        "total_visits": sum(daily.values()),
        "daily": [
            {"date": date.isoformat(), "count": daily[date.isoformat()]}
            for date in dates
        ],
        "top_sites": [
            {
                "site_id": row["site_id"],
                "name": row["name"],
                "url": row["url"],
                "logo_url": logo_url_for(row["logo_path"]),
                "visits": row["visits"],
            }
            for row in top_rows
        ],
        "groups": groups,
    }


def set_health(site_id: int, status: str, http_status: int | None, checked_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sites SET status = ?, http_status = ?, last_checked_at = ? WHERE id = ?",
            (status, http_status, checked_at, site_id),
        )


def reorder(items: Iterable[tuple[int, int]]) -> None:
    """Set sort_order for many sites in one transaction."""
    rows = list(items)
    if not rows:
        return
    now = _now()
    with _connect() as conn:
        conn.execute("BEGIN")
        for site_id, sort_order in rows:
            conn.execute(
                "UPDATE sites SET sort_order = ?, updated_at = ? WHERE id = ?",
                (sort_order, now, site_id),
            )
        conn.execute("COMMIT")


# ---------- tags ----------

def _set_tags(conn: sqlite3.Connection, site_id: int, names: list[str]) -> None:
    clean = sorted({n.strip() for n in names if n and n.strip()}, key=str.lower)
    conn.execute("DELETE FROM site_tags WHERE site_id = ?", (site_id,))
    for name in clean:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, ?)",
            (name, _now()),
        )
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if tag_row:
            conn.execute(
                "INSERT OR IGNORE INTO site_tags (site_id, tag_id) VALUES (?, ?)",
                (site_id, tag_row["id"]),
            )


def set_site_tags(site_id: int, names: list[str]) -> dict | None:
    with _connect() as conn:
        _set_tags(conn, site_id, names)
    return get_site(site_id)


def all_tags() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, COUNT(st.site_id) AS count
               FROM tags t LEFT JOIN site_tags st ON st.tag_id = t.id
               JOIN sites s ON s.id = st.site_id AND s.archived = 0
               GROUP BY t.id ORDER BY t.name COLLATE NOCASE"""
        ).fetchall()
    return [dict(r) for r in rows]


def list_groups() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(group_name, ''), '未分类') AS name, COUNT(*) AS count
               FROM sites WHERE archived = 0 GROUP BY name
               ORDER BY name = '未分类', name COLLATE NOCASE"""
        ).fetchall()
    return [dict(r) for r in rows]


# ---------- maintenance ----------

def backup_db(dest: Path) -> None:
    """Copy the live DB file (+ checkpoint WAL) to ``dest``."""
    with _connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    import shutil
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings.db_path, dest)


def referenced_logos() -> set[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT logo_path FROM sites WHERE logo_path != ''").fetchall()
    return {r["logo_path"] for r in rows}


def db_info() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        archived = conn.execute("SELECT COUNT(*) FROM sites WHERE archived=1").fetchone()[0]
        broken = conn.execute(
            "SELECT COUNT(*) FROM sites WHERE status IN ('unreachable','timeout','error')"
        ).fetchone()[0]
        tags = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
        ver = conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_version").fetchone()[0]
    return {
        "db_path": str(settings.db_path),
        "schema_version": ver,
        "sites": total,
        "archived": archived,
        "broken": broken,
        "tags": tags,
    }
