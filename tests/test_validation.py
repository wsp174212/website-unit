"""Input validation via the API."""


def test_empty_url(client):
    r = client.post("/api/sites", json={"url": "   "})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "EMPTY_URL"


def test_unsupported_scheme(client):
    r = client.post("/api/sites", json={"url": "file:///etc/passwd"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_SCHEME"


def test_malformed_url(client):
    r = client.post("/api/sites", json={"url": "https:///nohost"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_URL"


def test_duplicate_url(client):
    client.post("/api/sites", json={"url": "https://example.com"})
    r = client.post("/api/sites", json={"url": "https://example.com/"})  # same canonical
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SITE_ALREADY_EXISTS"


def test_long_name(client):
    long_name = "x" * 5000
    r = client.post("/api/sites", json={"url": "https://a.com", "name": long_name})
    assert r.status_code == 201
    assert len(r.json()["name"]) == 5000


def test_update_to_duplicate(client):
    a = client.post("/api/sites", json={"url": "https://a.com"}).json()
    client.post("/api/sites", json={"url": "https://b.com"})
    r = client.put(f"/api/sites/{a['id']}", json={"url": "https://b.com"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SITE_ALREADY_EXISTS"
