"""SSRF-safe HTTP fetcher for metadata + logo downloads.

Guarantees:
- only ``http``/``https`` schemes
- per-hop SSRF validation (including redirects) by resolving the hostname
  and inspecting the resolved IPs — defends against DNS rebind → private IP
- response body capped to a caller-specified size
- connect/read timeouts and a redirect cap

Local-first policy: ``allow_private_network_fetch`` defaults to True so LAN
and localhost sites remain navigable. Regardless of that flag, link-local
(169.254/16, fe80::/10), unspecified, multicast and reserved addresses are
always blocked — this closes cloud-metadata SSRF (169.254.169.254) even when
private fetch is allowed.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from .config import Settings, always_blocked_hosts, settings as global_settings
from .errors import ErrorCode, SiteUnitError


@dataclass
class FetchResult:
    status_code: int
    headers: dict
    content: bytes
    final_url: str
    truncated: bool = False
    content_type: str = field(default="")


def _resolve(host: str, port: int) -> list[str]:
    """Return resolved IP strings for ``host``. Empty list on DNS failure."""
    try:
        infos = socket.getaddrinfo(host, port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    out, seen = [], set()
    for fam, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def _ip_blocked(ip_str: str, allow_private: bool) -> tuple[bool, str]:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True, "invalid IP"
    # Always-blocked ranges (never legitimate nav targets).
    if ip.is_unspecified or ip.is_multicast or ip.is_reserved or ip.is_link_local:
        return True, f"blocked range {ip}"
    # Loopback / RFC1918 / CGNAT: gated by the local-first toggle.
    if ip.is_loopback or ip.is_private:
        if not allow_private:
            return True, f"private/loopback {ip} disallowed"
    return False, ""


def is_url_blocked(url: str, *, allow_private: bool) -> tuple[bool, str]:
    """Validate ``url`` for fetching. Returns (blocked, reason)."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return True, f"scheme {scheme or 'none'} not allowed"
    host = (parts.hostname or "").lower()
    if not host:
        return True, "missing host"
    if host in always_blocked_hosts():
        return True, f"metadata host {host} blocked"
    port = parts.port or (443 if scheme == "https" else 80)
    for ip_str in _resolve(host, port):
        blocked, reason = _ip_blocked(ip_str, allow_private)
        if blocked:
            return True, f"{host} resolves to {reason}"
    return False, ""


class SafeFetcher:
    """Thin httpx wrapper that enforces scheme + SSRF on every request hop."""

    def __init__(self, conf: Settings | None = None, *, transport=None):
        self.conf = conf or global_settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.conf.fetch_read_timeout, connect=self.conf.fetch_connect_timeout),
            follow_redirects=True,
            max_redirects=self.conf.fetch_redirect_limit,
            verify=self.conf.verify_tls,
            transport=transport,
            event_hooks={"request": [self._guard]},
        )

    async def _guard(self, request: httpx.Request) -> None:
        blocked, reason = is_url_blocked(str(request.url), allow_private=self.conf.allow_private_network_fetch)
        if blocked:
            raise SiteUnitError(ErrorCode.SSRF_BLOCKED, f"拒绝访问该地址：{reason}")

    async def fetch(self, url: str, *, max_bytes: int, headers: dict | None = None) -> FetchResult:
        # Pre-check the entry URL so we fail fast with a clear code before any
        # network activity (the hook re-checks each redirect hop too).
        blocked, reason = is_url_blocked(url, allow_private=self.conf.allow_private_network_fetch)
        if blocked:
            raise SiteUnitError(ErrorCode.SSRF_BLOCKED, f"拒绝访问该地址：{reason}")

        h = {"User-Agent": _UA}
        if headers:
            h.update(headers)
        collected = bytearray()
        truncated = False
        status_code = 0
        headers: dict = {}
        final_url = url
        ctype = ""
        async with self._client.stream("GET", url, headers=h) as resp:
            status_code = resp.status_code
            headers = dict(resp.headers)
            final_url = str(resp.url)
            ctype = resp.headers.get("content-type", "")
            async for chunk in resp.aiter_bytes():
                if len(collected) + len(chunk) > max_bytes:
                    collected.extend(chunk[: max_bytes - len(collected)])
                    truncated = True
                    break
                collected.extend(chunk)
        return FetchResult(
            status_code=status_code,
            headers=headers,
            content=bytes(collected),
            final_url=final_url,
            truncated=truncated,
            content_type=ctype,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SiteUnitBot/1.0"
)
