from app import db


def test_init_creates_tables_and_backfills_normalized():
    db.init_db()
    info = db.db_info()
    assert info["schema_version"] == 2
    assert info["sites"] == 0


def test_insert_and_get():
    db.init_db()
    s = db.insert_site(name="Test", url="https://example.com", description="d",
                       group_name="g", logo_path="x.png", logo_source="page", tags=["a", "b"])
    assert s["id"]
    assert s["normalized_url"] == "https://example.com"
    assert s["tags"] == ["a", "b"]
    fetched = db.get_site(s["id"])
    assert fetched["name"] == "Test"
    assert fetched["tags"] == ["a", "b"]


def test_dedup_by_normalized_url():
    db.init_db()
    db.insert_site(name="A", url="https://example.com", description="",
                   group_name="", logo_path="", logo_source="", tags=[])
    assert db.get_by_normalized_url("example.com/") is not None
    assert db.get_by_normalized_url("https://example.com#x") is not None


def test_delete_cascades_tags():
    db.init_db()
    s = db.insert_site(name="T", url="https://t.com", description="",
                       group_name="", logo_path="", logo_source="", tags=["x", "y"])
    assert db.all_tags()  # tag exists
    db.delete_site(s["id"])
    # site_tags rows gone (cascade), tag row may linger but unlinked
    assert db.get_site(s["id"]) is None


def test_ordering():
    db.init_db()
    a = db.insert_site(name="Apple", url="https://a.com", description="",
                       group_name="g", logo_path="", logo_source="", tags=[])
    b = db.insert_site(name="Banana", url="https://b.com", description="",
                       group_name="g", logo_path="", logo_source="", tags=[])
    db.update_site(b["id"], {"sort_order": 0})
    db.update_site(a["id"], {"sort_order": 10})
    order = [s["id"] for s in db.list_sites(order="custom")]
    assert order == [b["id"], a["id"]]  # lower sort_order first


def test_name_order():
    db.init_db()
    db.insert_site(name="Zebra", url="https://z.com", description="",
                   group_name="", logo_path="", logo_source="", tags=[])
    db.insert_site(name="Apple", url="https://a.com", description="",
                   group_name="", logo_path="", logo_source="", tags=[])
    names = [s["name"] for s in db.list_sites(order="name")]
    assert names == ["Apple", "Zebra"]


def test_visit_increments():
    db.init_db()
    s = db.insert_site(name="V", url="https://v.com", description="",
                       group_name="", logo_path="", logo_source="", tags=[])
    assert db.visit_site(s["id"])
    assert db.visit_site(s["id"])
    assert db.get_site(s["id"])["visit_count"] == 2
    assert db.get_site(s["id"])["last_visited_at"]


def test_tag_filter():
    db.init_db()
    db.insert_site(name="A", url="https://a.com", description="",
                   group_name="", logo_path="", logo_source="", tags=["coding"])
    db.insert_site(name="B", url="https://b.com", description="",
                   group_name="", logo_path="", logo_source="", tags=["news"])
    res = db.list_sites(tag="coding")
    assert len(res) == 1 and res[0]["name"] == "A"


def test_archived_hidden_by_default():
    db.init_db()
    s = db.insert_site(name="A", url="https://a.com", description="",
                       group_name="", logo_path="", logo_source="", tags=[])
    db.update_site(s["id"], {"archived": True})
    assert db.list_sites(archived=False) == []
    assert len(db.list_sites(archived=True)) == 1
    assert len(db.list_sites(archived=None)) == 1
