"""Fetch a site's page title and favicon/logo.

Strategy, in order of preference:
1. Icons declared in the page HTML (rel=icon / apple-touch-icon / shortcut icon / og:image)
2. <site-root>/favicon.ico
3. Public favicon services (DuckDuckGo, then Google) as a last resort
"""

import re

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SiteUnitLogoBot/1.0"
)

REQUEST_TIMEOUT = 10.0
MAX_LOGO_BYTES = 512 * 1024

_CONTENT_TYPE_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/ico": "ico",
    "image/x-ico": "ico",
}

def normalize_url(raw: str) -> str:
    """Turn 'example.com/x' into 'https://example.com/x'."""
    raw = raw.strip()
    if not raw:
        raise ValueError("URL 不能为空")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = "https://" + raw
    return raw


def _pick_extension(content_type: str, body: bytes) -> str | None:
    ctype = content_type.split(";")[0].strip().lower()
    if ctype in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[ctype]
    if ctype.startswith("image/"):
        return ctype.split("/")[1].split("+")[0] or None
    # Some servers serve favicons with wrong or missing content types.
    if body[:4] == b"\x89PNG":
        return "png"
    if body[:3] == b"\xff\xd8\xff":
        return "jpg"
    if body[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "webp"
    if body[:1] == b"<" and (b"svg" in body[:512].lower() or b"<svg" in body[:512].lower()):
        return "svg"
    if len(body) >= 2 and body[:2] == b"\x00\x00":
        return "ico"
    return None


def _candidate_icon_urls(page_url: str, html: str) -> list[str]:
    """Extract icon URLs declared in the page, most specific first."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    links = soup.find_all("link")
    icons = []
    for l in links:
        rels = l.get("rel") or []
        rel_text = " ".join(str(r).lower() for r in rels)
        if rel_text in ("icon", "shortcut icon", "apple-touch-icon",
                        "apple-touch-icon-precomposed", "mask-icon", "fluid-icon"):
            icons.append(l)
    # Prefer apple-touch-icon (usually larger), then icon, then the rest.
    def _priority(link) -> int:
        rel_text = " ".join(str(r).lower() for r in (link.get("rel") or []))
        order = ["apple-touch-icon-precomposed", "apple-touch-icon", "icon",
                 "shortcut icon", "fluid-icon", "mask-icon"]
        for i, name in enumerate(order):
            if name in rel_text:
                return i
        return len(order)

    icons.sort(key=_priority)
    for link in icons:
        href = link.get("href")
        if not href:
            continue
        # apple-touch-icon etc. may use sizes/srcset hints; href alone is fine.
        candidates.append(_urljoin(page_url, href))

    og = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "og:image"}
    )
    if og and og.get("content"):
        candidates.append(_urljoin(page_url, og["content"]))

    # Deduplicate while preserving order.
    seen, unique = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _urljoin(base: str, href: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base, href.strip())


def _page_title(soup: BeautifulSoup, page_url: str) -> str:
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)[:120]
    og = soup.find("meta", attrs={"property": "og:site_name"})
    if og and og.get("content"):
        return og["content"][:120]
    from urllib.parse import urlparse

    return urlparse(page_url).netloc.removeprefix("www.")


async def _try_download_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str] | None:
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    body = resp.content[:MAX_LOGO_BYTES]
    if not body:
        return None
    ext = _pick_extension(resp.headers.get("content-type", ""), resp.content[:64])
    if ext is None:
        return None
    return body, ext


async def fetch_site_meta(client: httpx.AsyncClient, url: str) -> dict:
    """Return {'title': str, 'logo': bytes|None, 'ext': str|None}. Never raises for network misses."""
    result = {"title": "", "logo": None, "ext": None}
    page_html: str | None = None

    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT})
        if resp.status_code < 400 and "text/html" in resp.headers.get("content-type", ""):
            page_html = resp.text
    except httpx.HTTPError:
        page_html = None

    from urllib.parse import urlparse

    if page_html is not None:
        soup = BeautifulSoup(page_html, "html.parser")
        result["title"] = _page_title(soup, str(resp.url))
        for icon_url in _candidate_icon_urls(str(resp.url), page_html):
            got = await _try_download_image(client, icon_url)
            if got:
                result["logo"], result["ext"] = got
                return result
    else:
        result["title"] = urlparse(url).netloc.removeprefix("www.")

    root = f"{urlparse(url).scheme}://{urlparse(url).netloc}/favicon.ico"
    got = await _try_download_image(client, root)
    if got and got[0] not in (b"", None) and not got[0].startswith(b"<html"):
        result["logo"], result["ext"] = got
        return result

    domain = urlparse(url).netloc
    got = await _try_download_image(client, f"https://icons.duckduckgo.com/ip3/{domain}.ico")
    if got:
        result["logo"], result["ext"] = got
        return result

    got = await _try_download_image(
        client, f"https://www.google.com/s2/favicons?sz=128&domain={domain}"
    )
    if got:
        result["logo"], result["ext"] = got
    return result
