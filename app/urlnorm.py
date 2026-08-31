"""URL normalization & canonicalization for dedup.

Rules (deliberately conservative to avoid merging different sites):

- add ``https://`` when no scheme is present
- reject non-http(s) schemes (file:, ftp:, data:, javascript: ...)
- lowercase the hostname (case-insensitive by DNS spec)
- strip default ports (:80 for http, :443 for https)
- drop the URL fragment (``#...``) — never identifies a distinct resource
- collapse a *root* path of ``/`` to empty (``example.com/`` == ``example.com``)
- keep the query string as-is (different queries can be different pages)

Both ``url`` and ``normalized_url`` are produced from these rules; the
canonical form is what we dedup on.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit, quote

from .errors import ErrorCode, SiteUnitError

_ALLOWED_SCHEMES = {"http", "https"}


def normalize_url(raw: str) -> str:
    """Return a canonical URL or raise SiteUnitError."""
    if raw is None:
        raise SiteUnitError(ErrorCode.EMPTY_URL, "URL 不能为空")
    s = raw.strip()
    if not s:
        raise SiteUnitError(ErrorCode.EMPTY_URL, "URL 不能为空")

    # Detect any "scheme:" prefix (with or without //) so data:/javascript:/
    # file: are rejected rather than mis-prefixed with https://.
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", s)
    if m:
        scheme = m.group(1).lower()
    else:
        scheme = "https"
        s = "https://" + s

    if scheme not in _ALLOWED_SCHEMES:
        raise SiteUnitError(
            ErrorCode.UNSUPPORTED_SCHEME,
            f"不支持的协议：{scheme}（仅支持 http/https）",
        )

    parts = urlsplit(s)
    if not parts.netloc:
        raise SiteUnitError(ErrorCode.INVALID_URL, "URL 缺少域名")
    host = (parts.hostname or "").lower()
    if not host:
        raise SiteUnitError(ErrorCode.INVALID_URL, "URL 缺少域名")

    try:
        port = parts.port
    except ValueError:
        raise SiteUnitError(ErrorCode.INVALID_URL, "URL 端口不合法")

    default_port = 443 if scheme == "https" else 80
    netloc = host
    if port and port != default_port:
        netloc = f"{host}:{port}"

    path = parts.path or ""
    if path == "/":
        path = ""
    # Don't touch other trailing slashes — /a and /a/ can be different pages.

    query = parts.query
    # fragment dropped on purpose
    rebuilt = urlunsplit((scheme, netloc, path, query, ""))
    return quote(rebuilt, safe="%/:?&=+$,#@!*'()")


def canonical_key(url: str) -> str:
    """Dedup key: same as normalize_url. Separated for clarity / future tweaking."""
    return normalize_url(url)


def host_of(url: str) -> str:
    try:
        return urlsplit(url).hostname or url
    except ValueError:
        return url


def looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
