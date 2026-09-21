"""Tests for visit event capture and statistics aggregation."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import config, db
from app.migrations import m001_baseline, m002_extend


def _insert_event(site_id: int, *, days_ago: int = 0) -> str:
    """Insert a historical event directly for deterministic aggregation."""
    visited_at = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat(timespec="seconds")
    with sqlite3.connect(config.settings.db_path) as conn:
        conn.execute(
            "INSERT INTO visit_events (site_id, visited_at) VALUES (?, ?)",
            (site_id, visited_at),
        )
    return visited_at


def _event_count(site_id: int | None = None) -> int:
    with sqlite3.connect(config.settings.db_path) as conn:
        if site_id is None:
            return conn.execute("SELECT COUNT(*) FROM visit_events").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM visit_events WHERE site_id = ?", (site_id,)
        ).fetchone()[0]


def test_visit_event_is_written_and_rolls_back_with_count(monkeypatch):
    db.init_db()
    site = db.insert_site(
        name="Visit", url="https://visit.example", description="",
        group_name="", logo_path="", logo_source="", tags=[],
    )

    def fail_event(*args, **kwargs):
        raise sqlite3.OperationalError("forced event failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(db, "record_visit_event", fail_event)
        with pytest.raises(sqlite3.OperationalError):
            db.visit_site(site["id"])

    assert db.get_site(site["id"])["visit_count"] == 0
    assert db.get_site(site["id"])["last_visited_at"] is None
    assert _event_count(site["id"]) == 0

    assert db.visit_site(site["id"])
    stored = db.get_site(site["id"])
    assert stored["visit_count"] == 1
    assert _event_count(site["id"]) == 1
    with sqlite3.connect(config.settings.db_path) as conn:
        event = conn.execute(
            "SELECT site_id, visited_at FROM visit_events WHERE site_id = ?",
            (site["id"],),
        ).fetchone()
    assert event[0] == site["id"]
    assert event[1] == stored["last_visited_at"]


def test_visit_missing_site_returns_404_and_writes_no_event(client):
    response = client.post("/api/sites/999/visit")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "SITE_NOT_FOUND", "message": "站点不存在"}
    }
    assert _event_count() == 0


def test_daily_buckets_have_exact_length_and_leading_zeros(client):
    payload = {"url": "https://daily.example", "name": "Daily"}
    created = client.post("/api/sites", json=payload).json()
    db.visit_site(created["id"])
    _insert_event(created["id"], days_ago=6)

    result = client.get("/api/stats/overview?days=7")
    assert result.status_code == 200
    body = result.json()
    today = datetime.now(timezone.utc).date()
    first = today - timedelta(days=6)
    expected_dates = [(first + timedelta(days=i)).isoformat() for i in range(7)]

    assert body["days"] == 7
    assert [item["date"] for item in body["daily"]] == expected_dates
    assert len(body["daily"]) == 7
    assert body["daily"][0]["count"] == 1
    assert all(item["count"] == 0 for item in body["daily"][1:6])
    assert body["daily"][-1]["count"] == 1
    assert body["total_visits"] == 2


def test_top_sites_limit_order_and_nullable_logo(client):
    site_ids = []
    for index in range(12):
        group = "B" if index == 0 else ("" if index == 1 else ("A" if index == 2 else "D"))
        logo = "0000000000000000.png" if index == 0 else ""
        site = db.insert_site(
            name=f"Site {index}", url=f"https://site{index}.example", description="",
            group_name=group, logo_path=logo, logo_source="page" if logo else "", tags=[],
        )
        site_ids.append(site["id"])
        for _ in range(2 if index == 0 else 1):
            _insert_event(site["id"])

    result = client.get("/api/stats/overview?days=7").json()
    top = result["top_sites"]
    assert len(top) == 10
    assert top[0]["site_id"] == site_ids[0]
    assert top[0]["visits"] == 2
    assert top[0]["logo_url"] == "/logos/0000000000000000.png"
    assert top[1]["site_id"] == site_ids[1]
    assert top[1]["logo_url"] is None
    assert [item["site_id"] for item in top[1:]] == site_ids[1:10]
    assert [item["visits"] for item in top[1:]] == [1] * 9

    assert result["groups"] == [
        {"name": "D", "count": 9},
        {"name": "B", "count": 2},
        {"name": "A", "count": 1},
        {"name": "", "count": 1},
    ]


def test_days_whitelist_and_default(client):
    for days in (7, 30, 90):
        response = client.get(f"/api/stats/overview?days={days}")
        assert response.status_code == 200
        assert response.json()["days"] == days
        assert len(response.json()["daily"]) == days

    default = client.get("/api/stats/overview")
    assert default.status_code == 200
    assert default.json()["days"] == 30

    invalid = client.get("/api/stats/overview?days=8")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_archived_sites_and_deleted_sites_are_excluded(client):
    active = db.insert_site(
        name="Active", url="https://active.example", description="",
        group_name="Active", logo_path="", logo_source="", tags=[],
    )
    archived = db.insert_site(
        name="Archived", url="https://archived.example", description="",
        group_name="Archived", logo_path="", logo_source="", tags=[],
    )
    deleted = db.insert_site(
        name="Deleted", url="https://deleted.example", description="",
        group_name="Deleted", logo_path="", logo_source="", tags=[],
    )
    for site_id in (active["id"], archived["id"], deleted["id"]):
        _insert_event(site_id)

    db.update_site(archived["id"], {"archived": True})
    db.delete_site(deleted["id"])
    assert _event_count(deleted["id"]) == 0

    result = client.get("/api/stats/overview?days=7").json()
    assert result["total_visits"] == 1
    assert [item["site_id"] for item in result["top_sites"]] == [active["id"]]
    assert result["groups"] == [{"name": "Active", "count": 1}]


def test_v2_database_upgrades_to_v3_and_statistics_work():
    path = config.settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        m001_baseline(conn)
        m002_extend(conn)
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version(version) VALUES (1), (2)")
        conn.execute(
            """
            INSERT INTO sites
                (name, url, normalized_url, description, group_name, logo_path,
                 logo_source, favorite, pinned, sort_order, created_at, updated_at,
                 visit_count, status, archived)
            VALUES ('Legacy', 'https://legacy.example', 'https://legacy.example',
                    '', 'Legacy', '', '', 0, 0, 0, '2026-01-01T00:00:00+00:00',
                    '2026-01-01T00:00:00+00:00', 0, 'unknown', 0)
            """
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()
    assert db.db_info()["schema_version"] == 3
    assert db.visit_site(1)
    overview = db.stats_overview(7)
    assert overview["total_visits"] == 1
    assert overview["daily"][-1]["count"] == 1
    assert overview["top_sites"][0]["site_id"] == 1
    assert overview["groups"] == [{"name": "Legacy", "count": 1}]
