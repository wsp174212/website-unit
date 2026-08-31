"""SSRF guard tests — no real network, DNS is stubbed per test."""

import asyncio

import httpx
import pytest

from app import fetcher
from app.errors import ErrorCode, SiteUnitError


def _patch_dns(monkeypatch, ip):
    monkeypatch.setattr(fetcher, "_resolve", lambda host, port: [ip])


def test_blocks_non_http_scheme():
    blocked, _ = fetcher.is_url_blocked("file:///etc/passwd", allow_private=True)
    assert blocked


def test_blocks_loopback_when_strict(monkeypatch):
    _patch_dns(monkeypatch, "127.0.0.1")
    blocked, _ = fetcher.is_url_blocked("http://localhost/x", allow_private=False)
    assert blocked
    blocked, _ = fetcher.is_url_blocked("http://127.0.0.1/x", allow_private=False)
    assert blocked


def test_allows_loopback_when_local(monkeypatch):
    _patch_dns(monkeypatch, "127.0.0.1")
    blocked, _ = fetcher.is_url_blocked("http://127.0.0.1/x", allow_private=True)
    assert not blocked


def test_metadata_ip_always_blocked(monkeypatch):
    _patch_dns(monkeypatch, "169.254.169.254")
    for allow in (True, False):
        blocked, _ = fetcher.is_url_blocked("http://169.254.169.254/", allow_private=allow)
        assert blocked, f"metadata must be blocked when allow_private={allow}"


def test_blocks_private_when_strict(monkeypatch):
    _patch_dns(monkeypatch, "10.0.0.5")
    blocked, _ = fetcher.is_url_blocked("http://internal.example/", allow_private=False)
    assert blocked


def test_allows_private_when_local(monkeypatch):
    _patch_dns(monkeypatch, "192.168.1.1")
    blocked, _ = fetcher.is_url_blocked("http://router/", allow_private=True)
    assert not blocked


def test_allows_public(monkeypatch):
    _patch_dns(monkeypatch, "1.1.1.1")
    blocked, _ = fetcher.is_url_blocked("https://example.com/", allow_private=False)
    assert not blocked


def test_safe_fetcher_raises_on_blocked(monkeypatch):
    _patch_dns(monkeypatch, "127.0.0.1")
    from tests.helpers import make_fetcher

    def h(req):
        raise AssertionError("network must not be reached when blocked")

    f = make_fetcher(h, allow_private_network_fetch=False)
    with pytest.raises(SiteUnitError) as ei:
        asyncio.run(f.fetch("http://127.0.0.1/", max_bytes=10))
    assert ei.value.code == ErrorCode.SSRF_BLOCKED.value
    asyncio.run(f.aclose())


def test_safe_fetcher_caps_body(monkeypatch):
    _patch_dns(monkeypatch, "203.0.113.10")

    def h(req):
        return httpx.Response(200, content=b"x" * 1000)

    from tests.helpers import make_fetcher
    f = make_fetcher(h)
    r = asyncio.run(f.fetch("https://example.com/big", max_bytes=50))
    assert r.truncated is True
    assert len(r.content) == 50
    asyncio.run(f.aclose())
