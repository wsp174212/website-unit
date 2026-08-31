"""Shared test helpers (no fixtures) — importable from test modules."""

import sqlite3
from pathlib import Path

import httpx

from app import config, fetcher

LEGACY_V1_DDL = """
CREATE TABLE sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    grp         TEXT NOT NULL DEFAULT '',
    logo        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def make_legacy_db(path: Path) -> None:
    """Create a pre-migration v1 database (no schema_version table)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_V1_DDL)
    conn.execute(
        "INSERT INTO sites (name, url, description, grp, logo, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Example", "https://example.com", "a site", "tools", "abc.png", "2024-01-01", "2024-01-01"),
    )
    conn.commit()
    conn.close()


def make_fetcher(handler, **conf):
    """Build a SafeFetcher backed by an httpx MockTransport (no real network)."""
    overrides = {"fetch_connect_timeout": 2.0, "fetch_read_timeout": 2.0}
    overrides.update(conf)
    conf_obj = config.settings.apply(**overrides)
    transport = httpx.MockTransport(handler)
    return fetcher.SafeFetcher(conf_obj, transport=transport)
