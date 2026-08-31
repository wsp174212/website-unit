"""Migration safety: a legacy v1 DB must upgrade without data loss."""

from app import config, db
from tests.helpers import make_legacy_db


def test_legacy_db_upgrades(tmp_path):
    make_legacy_db(config.settings.db_path)
    db.init_db()

    info = db.db_info()
    assert info["schema_version"] == 2
    assert info["sites"] == 1

    s = db.get_site(1)
    # original data preserved
    assert s["name"] == "Example"
    assert s["url"] == "https://example.com"
    assert s["group_name"] == "tools"        # renamed from grp
    assert s["logo_path"] == "abc.png"       # renamed from logo
    # backfilled normalized key
    assert s["normalized_url"] == "https://example.com"
    # new columns have safe defaults
    assert s["favorite"] == 0
    assert s["pinned"] == 0
    assert s["archived"] == 0
    assert s["status"] == "unknown"
    assert s["visit_count"] == 0
    assert s["tags"] == []


def test_migrations_idempotent():
    db.init_db()
    db.init_db()  # second run is a no-op
    assert db.db_info()["schema_version"] == 2


def test_crud_after_migration():
    make_legacy_db(config.settings.db_path)
    db.init_db()
    # original site still dedup-checks correctly
    assert db.get_by_normalized_url("https://example.com") is not None
    # add a new site
    new = db.insert_site(name="New", url="https://new.com", description="",
                         group_name="g", logo_path="", logo_source="", tags=["t"])
    assert new["tags"] == ["t"]
    assert db.db_info()["sites"] == 2
