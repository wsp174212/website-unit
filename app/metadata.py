"""Metadata pipeline: URL → {title, description, logo}.

```
URL
 ↓ normalize
 fetch HTML (capped)
 ↓
 parse title / description / icon candidates
 ↓
 rank candidates
 ↓
 download + validate image
 ↓
 (fallbacks: /favicon.ico, DuckDuckGo, Google)
 ↓
 return {title, description, logo, ext, source}
```

Network misses never raise — they return empty/None so the caller can still
create the site with a letter-avatar fallback.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .config import settings
from .errors import ErrorCode, SiteUnitError
from .fetcher import FetchResult, SafeFetcher
from .logos import content_type_hint_to_ext, validate_logo
from .urlnorm import normalize_url

_TITLE_MAX = 200
_DESC_MAX = 400


def _decode_html(content: bytes, content_type: str) -> str:
    charset = None
    if "charset=" in content_type.lower():
        try:
            charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()
        except Exception:
            charset = None
    for enc in (charset, "utf-8"):
        if not enc:
            continue
        try:
            return content.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("latin-1", errors="replace")


def _looks_like_html(content: bytes, content_type: str) -> bool:
    if "html" in content_type.lower():
        return True
    head = content.lstrip()[:200].lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<head")


def _meta_content(soup: BeautifulSoup, *selectors) -> str:
    for sel in selectors:
        tag = soup.find("meta", attrs=sel)
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _title(soup: BeautifulSoup, final_url: str) -> str:
    og = _meta_content(soup, {"property": "og:title"}, {"name": "og:title"})
    if og:
        return og[:_TITLE_MAX]
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)[:_TITLE_MAX]
    site = _meta_content(soup, {"property": "og:site_name"}, {"name": "application-name"})
    if site:
        return site[:_TITLE_MAX]
    return (urlsplit(final_url).hostname or final_url).removeprefix("www.")


def _description(soup: BeautifulSoup) -> str:
    d = _meta_content(soup, {"property": "og:description"}, {"name": "description"},
                      {"name": "og:description"})
    return d[:_DESC_MAX]


_REL_ICON = {
    "icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed",
    "mask-icon", "fluid-icon",
}
# Higher score = preferred.
_REL_PRIORITY = {
    "apple-touch-icon-precomposed": 100,
    "apple-touch-icon": 90,
    "fluid-icon": 70,
    "icon": 50,
    "shortcut icon": 40,
    "mask-icon": 20,
}


def _size_score(link) -> int:
    sizes = link.get("sizes") or "0x0"
    m = re.search(r"(\d+)x(\d+)", str(sizes).lower())
    if m:
        return int(m.group(1)) * int(m.group(2))
    if str(sizes).lower() == "any":
        return 64 * 64
    return 0


def _icon_candidates(page_url: str, soup: BeautifulSoup) -> list[str]:
    cands: list[tuple[int, str]] = []
    for link in soup.find_all("link"):
        rels = [str(r).lower() for r in (link.get("rel") or [])]
        rel_text = " ".join(rels)
        priority = 0
        for name, score in _REL_PRIORITY.items():
            if name in rel_text:
                priority = max(priority, score)
        if priority == 0:
            continue
        href = link.get("href")
        if not href:
            continue
        full = urljoin(page_url, href.strip())
        # tie-break: larger declared size preferred
        cands.append((priority, _size_score(link), full))

    og_img = _meta_content(soup, {"property": "og:image"}, {"name": "og:image"})
    if og_img:
        cands.append((10, 0, urljoin(page_url, og_img)))

    # Sort: priority desc, then size desc, dedup by URL preserving best rank.
    cands.sort(key=lambda t: (-t[0], -t[1]))
    seen, ordered = set(), []
    for _, _, url in cands:
        if url and url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def _fallback_chain(final_url: str) -> list[tuple[str, str]]:
    """Return [(url, source), ...] tried after page-declared icons."""
    parts = urlsplit(final_url)
    domain = parts.hostname or ""
    root = f"{parts.scheme}://{parts.netloc}/favicon.ico"
    return [
        (root, "favicon"),
        (f"https://icons.duckduckgo.com/ip3/{domain}.ico", "ddg"),
        (f"https://www.google.com/s2/favicons?sz=128&domain={domain}", "google"),
    ]


async def _try_icon(fetcher: SafeFetcher, url: str) -> tuple[bytes, str] | None:
    try:
        r = await fetcher.fetch(url, max_bytes=settings.max_logo_size)
    except SiteUnitError:
        raise  # SSRF must propagate, not be swallowed into "no logo"
    except Exception:
        return None
    if r.status_code != 200 or not r.content:
        return None
    ext = validate_logo(r.content)
    if ext is None:
        # Some servers send a valid image with a wrong content-type and no
        # recognizable magic bytes; the validate guard already rejected it.
        return None
    return r.content, ext


async def fetch_site_meta(fetcher: SafeFetcher, raw_url: str) -> dict:
    """Return {title, description, logo: bytes|None, ext: str|None, source: str}."""
    url = normalize_url(raw_url)
    result: dict = {"title": "", "description": "", "logo": None, "ext": None, "source": ""}

    html: str | None = None
    final_url = url
    try:
        r = await fetcher.fetch(url, max_bytes=settings.max_html_size)
        final_url = r.final_url
        if r.status_code < 400 and _looks_like_html(r.content, r.content_type):
            html = _decode_html(r.content, r.content_type)
    except SiteUnitError:
        raise
    except Exception:
        html = None

    if html is not None:
        soup = BeautifulSoup(html, "html.parser")
        result["title"] = _title(soup, final_url)
        result["description"] = _description(soup)
        for icon_url in _icon_candidates(final_url, soup):
            got = await _try_icon(fetcher, icon_url)
            if got:
                result["logo"], result["ext"] = got
                result["source"] = "page"
                return result
    else:
        result["title"] = (urlsplit(url).hostname or url).removeprefix("www.")

    for fb_url, source in _fallback_chain(final_url):
        got = await _try_icon(fetcher, fb_url)
        if got:
            result["logo"], result["ext"] = got
            result["source"] = source
            return result
    return result
