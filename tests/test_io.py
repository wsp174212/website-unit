"""Import / export / backup tests."""

import io as _io
import zipfile

from app import config, db


def _make(client, url, **kw):
    return client.post("/api/sites", json={"url": url, "name": kw.get("name", ""),
                          "description": kw.get("description", ""), "group": kw.get("group", ""),
                          "tags": kw.get("tags", [])}).json()


def test_export_json(client):
    _make(client, "https://a.com", name="A")
    _make(client, "https://b.com", name="B")
    r = client.get("/api/io/export.json")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert len(data["sites"]) == 2
    assert "exported_at" in data


def test_import_json_merge(client):
    _make(client, "https://a.com")
    payload = {"version": 1, "exported_at": "x", "groups": [], "tags": [],
               "sites": [
                   {"url": "https://a.com", "name": "A", "description": "", "group": "", "tags": []},
                   {"url": "https://b.com", "name": "B", "description": "", "group": "", "tags": []},
               ]}
    r = client.post("/api/io/import/json?mode=merge", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["added"] == 1
    assert res["duplicates"] == 1
    assert len(client.get("/api/sites").json()) == 2


def test_import_json_replace(client):
    _make(client, "https://a.com")
    _make(client, "https://b.com")
    payload = {"version": 1, "exported_at": "x", "groups": [], "tags": [],
               "sites": [{"url": "https://c.com", "name": "C", "description": "", "group": "", "tags": []}]}
    r = client.post("/api/io/import/json?mode=replace", json=payload)
    assert r.json()["added"] == 1
    sites = client.get("/api/sites").json()
    assert len(sites) == 1 and sites[0]["url"] == "https://c.com"


def test_csv_roundtrip(client):
    _make(client, "https://a.com", name="A", group="g", tags=["t"])
    csv_text = client.get("/api/io/export.csv").content.decode("utf-8-sig")
    # wipe then reimport
    client.post("/api/sites/bulk", json={"action": "delete", "ids": [s["id"] for s in client.get("/api/sites").json()]})
    r = client.post("/api/io/import/csv?mode=merge",
                    files={"file": ("exp.csv", csv_text.encode("utf-8"), "text/csv")})
    assert r.json()["added"] == 1
    s = client.get("/api/sites").json()[0]
    assert s["name"] == "A" and s["group"] == "g" and s["tags"] == ["t"]


def test_bookmarks_import(client):
    html = """<DL><DT><H3>Folder1</H3>
    <DL>
        <DT><A HREF="https://a.com">A</A>
        <DT><A HREF="https://b.com">B</A>
        <DT><A HREF="javascript:void(0)">skip</A>
    </DL></DT></DL>"""
    r = client.post("/api/io/import/bookmarks?mode=merge",
                    files={"file": ("bm.html", html.encode("utf-8"), "text/html")})
    res = r.json()
    assert res["added"] == 2
    sites = {s["url"] for s in client.get("/api/sites").json()}
    assert "https://a.com" in sites and "https://b.com" in sites
    assert client.get("/api/sites?q=group:Folder1").json().__len__() == 2


def test_backup_restore_roundtrip(client):
    s = _make(client, "https://a.com", name="A")
    # attach a logo file to prove logos survive the roundtrip
    logo_name = "aaaaaaaaaaaaaaaa.png"
    (config.settings.logo_dir / logo_name).write_bytes(b"\x89PNG\r\n\x1a\n")
    db.update_site(s["id"], {"logo_path": logo_name})

    zip_bytes = client.get("/api/io/backup").content
    assert zipfile.is_zipfile(_io.BytesIO(zip_bytes))

    # destroy current data
    client.post("/api/sites/bulk", json={"action": "delete", "ids": [s["id"]]})
    (config.settings.logo_dir / logo_name).unlink(missing_ok=True)
    assert client.get("/api/sites").json() == []

    # restore
    r = client.post("/api/io/restore", files={"file": ("b.zip", zip_bytes, "application/zip")})
    assert r.status_code == 200
    sites = client.get("/api/sites").json()
    assert len(sites) == 1 and sites[0]["name"] == "A"
    assert (config.settings.logo_dir / logo_name).exists()


def test_restore_rejects_path_traversal(client):
    bad = _io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
    bad.seek(0)
    r = client.post("/api/io/restore", files={"file": ("b.zip", bad.read(), "application/zip")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_ARCHIVE"
