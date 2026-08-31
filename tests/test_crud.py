"""CRUD via the HTTP API (metadata fetch is stubbed in conftest)."""


def _create(client, url="https://example.com", **kw):
    body = {"url": url, "name": kw.get("name", ""), "description": kw.get("description", ""),
            "group": kw.get("group", ""), "tags": kw.get("tags", [])}
    r = client.post("/api/sites", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_read_list(client):
    s = _create(client, group="g", tags=["a"])
    assert s["url"] == "https://example.com"
    assert s["group"] == "g"
    assert s["tags"] == ["a"]
    assert s["logo_url"] is None
    got = client.get(f"/api/sites/{s['id']}").json()
    assert got["name"] == s["name"]
    lst = client.get("/api/sites").json()
    assert len(lst) == 1


def test_update_site(client):
    s = _create(client)
    r = client.put(f"/api/sites/{s['id']}", json={"name": "New", "group": "x", "tags": ["t"]})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New"
    assert body["group"] == "x"
    assert body["tags"] == ["t"]


def test_delete_site(client):
    s = _create(client)
    r = client.delete(f"/api/sites/{s['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/sites/{s['id']}").status_code == 404


def test_visit(client):
    s = _create(client)
    r = client.post(f"/api/sites/{s['id']}/visit")
    assert r.status_code == 200
    assert r.json()["visit_count"] == 1
    r2 = client.post(f"/api/sites/{s['id']}/visit")
    assert r2.json()["visit_count"] == 2


def test_reorder(client):
    a = _create(client, "https://a.com")
    b = _create(client, "https://b.com")
    r = client.post("/api/sites/reorder", json={"items": [
        {"site_id": a["id"], "sort_order": 5}, {"site_id": b["id"], "sort_order": 1}]})
    assert r.status_code == 200
    order = [s["id"] for s in client.get("/api/sites?order=custom").json()]
    assert order == [b["id"], a["id"]]


def test_bulk_move_group(client):
    a = _create(client, "https://a.com")
    b = _create(client, "https://b.com")
    r = client.post("/api/sites/bulk", json={"action": "move_group", "ids": [a["id"], b["id"]], "group": "AI"})
    assert r.status_code == 200
    assert r.json()["affected"] == 2
    for sid in (a["id"], b["id"]):
        assert client.get(f"/api/sites/{sid}").json()["group"] == "AI"


def test_bulk_delete(client):
    a = _create(client, "https://a.com")
    b = _create(client, "https://b.com")
    r = client.post("/api/sites/bulk", json={"action": "delete", "ids": [a["id"], b["id"]]})
    assert r.json()["affected"] == 2
    assert client.get("/api/sites").json() == []


def test_bulk_archive(client):
    a = _create(client, "https://a.com")
    client.post("/api/sites/bulk", json={"action": "archive", "ids": [a["id"]]})
    assert client.get("/api/sites").json() == []
    assert len(client.get("/api/sites?archived=true").json()) == 1
    client.post("/api/sites/bulk", json={"action": "unarchive", "ids": [a["id"]]})
    assert len(client.get("/api/sites").json()) == 1


def test_search_tokens(client):
    _create(client, "https://a.com", name="Claude", group="AI", tags=["llm"])
    _create(client, "https://b.com", name="GitHub", group="Dev", tags=["git"])
    r = client.get("/api/sites?q=group:AI").json()
    assert len(r) == 1 and r[0]["name"] == "Claude"
    r = client.get("/api/sites?q=tag:llm").json()
    assert len(r) == 1
    r = client.get("/api/sites?q=claude").json()
    assert len(r) == 1 and r[0]["name"] == "Claude"


def test_404_envelope(client):
    r = client.get("/api/sites/9999")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "SITE_NOT_FOUND"
