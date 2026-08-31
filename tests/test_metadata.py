"""Metadata pipeline tests with a mocked HTTP transport (no real network)."""

import httpx
from app.metadata import fetch_site_meta
from tests.helpers import make_fetcher

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24  # valid magic, validate_logo accepts


def _png_resp():
    return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)


def html_resp(body):
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                          content=body.encode("utf-8"))


def fetch(handler, url):
    f = make_fetcher(handler)
    import asyncio
    try:
        return asyncio.run(fetch_site_meta(f, url))
    finally:
        asyncio.run(f.aclose())


def test_title_and_relative_favicon():
    def h(req):
        if req.url.path == "/":
            return html_resp("<html><head><title>My Site</title>"
                             "<link rel='icon' href='/icons/fav.ico'></head></html>")
        if req.url.path == "/icons/fav.ico":
            return _png_resp()
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["title"] == "My Site"
    assert m["logo"] == PNG
    assert m["source"] == "page"


def test_og_title_and_absolute_icon():
    def h(req):
        if "cdn" in req.url.host:
            return _png_resp()
        return html_resp("<html><head>"
                         "<meta property='og:title' content='OG Title'>"
                         "<meta property='og:image' content='https://cdn.x.com/og.png'>"
                         "</head></html>")
    m = fetch(h, "https://example.com")
    assert m["title"] == "OG Title"
    assert m["logo"] == PNG
    assert m["source"] == "page"


def test_apple_touch_preferred_over_icon():
    calls = []
    def h(req):
        calls.append(req.url.path)
        if "apple" in req.url.path:
            return _png_resp()
        if "icon" in req.url.path:
            return httpx.Response(200, content=b"not really", headers={"content-type": "image/png"})
        return html_resp("<link rel='apple-touch-icon' href='/apple.png'>"
                         "<link rel='icon' href='/icon.png'>")
    m = fetch(h, "https://example.com")
    # apple-touch should be attempted first; once it yields a valid PNG we stop.
    assert m["logo"] == PNG
    assert calls[1] == "/apple.png"  # [0]=page, [1]=apple-touch


def test_no_icon_falls_back_to_favicon():
    def h(req):
        if req.url.path == "/":
            return html_resp("<html><head><title>No Icon</title></head></html>")
        if req.url.path == "/favicon.ico":
            return _png_resp()
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["title"] == "No Icon"
    assert m["logo"] == PNG
    assert m["source"] == "favicon"


def test_no_icon_anywhere():
    def h(req):
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["title"] == "example.com"
    assert m["logo"] is None


def test_redirect_then_icon():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(302, headers={"location": "/home"})
        if req.url.path == "/home":
            return html_resp("<title>Redirected</title><link rel='icon' href='/home/i.ico'>")
        if req.url.path == "/home/i.ico":
            return _png_resp()
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["title"] == "Redirected"
    assert m["logo"] == PNG


def test_404_page_falls_back_to_favicon():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(404)
        if req.url.path == "/favicon.ico":
            return _png_resp()
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["title"] == "example.com"
    assert m["logo"] == PNG
    assert m["source"] == "favicon"


def test_500_page():
    def h(req):
        return httpx.Response(500)
    m = fetch(h, "https://example.com")
    assert m["title"] == "example.com"
    assert m["logo"] is None


def test_timeout():
    def h(req):
        raise httpx.TimeoutException("timed out")
    m = fetch(h, "https://example.com")
    assert m["title"] == "example.com"
    assert m["logo"] is None


def test_invalid_html():
    def h(req):
        return html_resp("<html><head><title>Bad</title<link rel=icon href=/i.ico>")
    m = fetch(h, "https://example.com")
    assert m["title"] == "Bad"


def test_html_as_image_rejected():
    # an icon URL that actually returns HTML must not be saved as a logo
    def h(req):
        if req.url.path == "/":
            return html_resp("<link rel=icon href='/fake.ico'>")
        if req.url.path == "/fake.ico":
            return html_resp("<html><body>not an image</body></html>")
        if req.url.path == "/favicon.ico":
            return _png_resp()
        return httpx.Response(404)
    m = fetch(h, "https://example.com")
    assert m["logo"] == PNG
    assert m["source"] == "favicon"  # fell back past the HTML-pretending icon
