"""Health check & batch refresh tests (network mocked)."""

import httpx

from app import services
from app.fetcher import FetchResult


class FakeFetcher:
    def __init__(self, *a, **k): pass

    async def fetch(self, url, max_bytes=1):
        if "unreachable" in url:
            raise httpx.ConnectError("no route")
        if "timeout" in url:
            raise httpx.TimeoutException("slow")
        if "500" in url:
            return FetchResult(500, {}, b"", url)
        return FetchResult(200, {}, b"", url)

    async def aclose(self): pass


def _make(client, host):
    return client.post("/api/sites", json={"url": f"https://{host}.com"}).json()


def test_health_check_classifies(client, monkeypatch):
    monkeypatch.setattr(services, "SafeFetcher", FakeFetcher)
    ok = _make(client, "ok")
    un = _make(client, "unreachable")
    to = _make(client, "timeout")
    er = _make(client, "500")
    r = client.post("/api/health/check", json={"ids": [ok["id"], un["id"], to["id"], er["id"]]})
    assert r.status_code == 200
    res = {x["id"]: x["status"] for x in r.json()["results"]}
    assert res[ok["id"]] == "healthy"
    assert res[un["id"]] == "unreachable"
    assert res[to["id"]] == "timeout"
    assert res[er["id"]] == "error"
    # persisted to db
    from app import db
    assert db.get_site(ok["id"])["status"] == "healthy"


def test_broken_view(client, monkeypatch):
    monkeypatch.setattr(services, "SafeFetcher", FakeFetcher)
    ok = _make(client, "ok")
    bad = _make(client, "unreachable")
    client.post("/api/health/check", json={"ids": [ok["id"], bad["id"]]})
    broken = client.get("/api/health/broken").json()
    ids = {s["id"] for s in broken}
    assert bad["id"] in ids and ok["id"] not in ids


def test_refresh_metadata_bulk(client, monkeypatch):
    s = _make(client, "https://example.com")

    async def fake_meta(fetcher, url):
        return {"title": "Fresh Title", "description": "fresh", "logo": None, "ext": None, "source": ""}
    monkeypatch.setattr(services, "fetch_site_meta", fake_meta)
    r = client.post("/api/health/refresh-metadata", json=[s["id"]])
    assert r.status_code == 200
    assert r.json()["updated"] == 1
    assert client.get(f"/api/sites/{s['id']}").json()["name"] == "Fresh Title"
