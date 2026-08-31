from app.urlnorm import normalize_url, canonical_key, host_of
from app.errors import SiteUnitError, ErrorCode
import pytest


def test_adds_scheme():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("example.com/a/b?q=1") == "https://example.com/a/b?q=1"


def test_keeps_http():
    assert normalize_url("http://example.com").startswith("http://")


def test_lowercases_host():
    assert normalize_url("https://EXAMPLE.com/Path").split("//")[1].startswith("example.com")


def test_strips_default_port():
    assert normalize_url("https://example.com:443/") == "https://example.com"
    assert normalize_url("http://example.com:80/") == "http://example.com"


def test_keeps_custom_port():
    assert normalize_url("https://example.com:8443/") == "https://example.com:8443"


def test_drops_fragment():
    assert "#abc" not in normalize_url("https://example.com/page#abc")


def test_root_slash_collapsed():
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("https://example.com/a/") == "https://example.com/a/"  # non-root kept


def test_keeps_query():
    assert normalize_url("https://example.com/?x=1") == "https://example.com?x=1"


def test_dedup_equivalence():
    a = canonical_key("example.com")
    b = canonical_key("https://example.com/")
    c = canonical_key("https://example.com/#x")
    assert a == b == c


def test_rejects_bad_schemes():
    for bad in ("file:///etc/passwd", "ftp://x", "data:text/plain,hi", "javascript:alert(1)"):
        with pytest.raises(SiteUnitError) as ei:
            normalize_url(bad)
        assert ei.value.code == ErrorCode.UNSUPPORTED_SCHEME.value


def test_empty_url():
    with pytest.raises(SiteUnitError) as ei:
        normalize_url("   ")
    assert ei.value.code == ErrorCode.EMPTY_URL.value


def test_host_of():
    assert host_of("https://www.example.com/x") == "www.example.com"
