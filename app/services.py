"""Service layer: orchestrates fetcher + metadata + logos + db.

Keeps route handlers thin and centralizes the "fetch metadata, save logo,
persist" pipeline so create / update / refetch / bulk-refresh share one path.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from . import db
from .config import settings
from .errors import ErrorCode, SiteUnitError
from .fetcher import SafeFetcher
from .logos import remove_logo, save_logo
from .metadata import fetch_site_meta
from .schemas import SiteCreate, SiteUpdate, serialize_site
from .urlnorm import normalize_url, canonical_key

log = logging.getLogger("siteunit.services")


async def _fetch_meta(url: str, fetcher: SafeFetcher | None = None) -> dict:
    own = fetcher is None
    if fetcher is None:
        fetcher = SafeFetcher()
    try:
        return await fetch_site_meta(fetcher, url)
    finally:
        if own:
            await fetcher.aclose()


async def create_site(payload: SiteCreate) -> dict:
    url = normalize_url(payload.url)
    if db.get_by_normalized_url(url):
        raise SiteUnitError(
            ErrorCode.SITE_ALREADY_EXISTS,
            "该站点已存在，无法重复添加",
            409,
        )
    meta = await _fetch_meta(url)
    logo_path = ""
    logo_source = ""
    if meta["logo"]:
        logo_path = save_logo(meta["logo"], meta["ext"], url=url)
        logo_source = meta["source"]
    name = payload.name.strip() or meta["title"] or url
    site = db.insert_site(
        name=name, url=url, description=payload.description.strip() or meta["description"],
        group_name=payload.group.strip(), logo_path=logo_path, logo_source=logo_source,
        tags=payload.tags,
    )
    return serialize_site(site)


async def update_site_record(site_id: int, payload: SiteUpdate) -> dict:
    site = db.get_site(site_id)
    if site is None:
        raise SiteUnitError(ErrorCode.SITE_NOT_FOUND, "站点不存在", 404)

    fields: dict = {}
    if payload.url is not None:
        new_url = normalize_url(payload.url)
        if new_url != site["url"]:
            existing = db.get_by_normalized_url(new_url)
            if existing and existing["id"] != site_id:
                raise SiteUnitError(ErrorCode.SITE_ALREADY_EXISTS, "该 URL 已被其他站点占用", 409)
            fields["url"] = new_url
            payload.refetch_metadata = True
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.description is not None:
        fields["description"] = payload.description.strip()
    if payload.group is not None:
        fields["group_name"] = payload.group.strip()
    if payload.favorite is not None:
        fields["favorite"] = 1 if payload.favorite else 0
    if payload.pinned is not None:
        fields["pinned"] = 1 if payload.pinned else 0
    if payload.archived is not None:
        fields["archived"] = 1 if payload.archived else 0
    if payload.tags is not None:
        fields["tags"] = payload.tags

    if payload.refetch_metadata:
        url = fields.get("url", site["url"])
        meta = await _fetch_meta(url)
        if meta["logo"]:
            new_path = save_logo(meta["logo"], meta["ext"], url=url)
            remove_logo(site.get("logo_path"))
            fields["logo_path"] = new_path
            fields["logo_source"] = meta["source"]
        # refresh title/description only when the user didn't set them explicitly
        if payload.name is None and meta["title"]:
            fields["name"] = meta["title"]
        if payload.description is None and meta["description"]:
            fields["description"] = meta["description"]

    updated = db.update_site(site_id, fields)
    return serialize_site(updated or site)


async def refetch_logo(site_id: int) -> dict:
    site = db.get_site(site_id)
    if site is None:
        raise SiteUnitError(ErrorCode.SITE_NOT_FOUND, "站点不存在", 404)
    meta = await _fetch_meta(site["url"])
    if not meta["logo"]:
        raise SiteUnitError(ErrorCode.LOGO_FETCH_FAILED, "无法获取该站点的 logo，可稍后重试", 422)
    new_path = save_logo(meta["logo"], meta["ext"], url=site["url"])
    remove_logo(site.get("logo_path"))
    updated = db.update_site(site_id, {"logo_path": new_path, "logo_source": meta["source"]})
    return serialize_site(updated or site)


async def refresh_metadata_bulk(ids: list[int]) -> dict:
    sem = asyncio.Semaphore(settings.health_concurrency)
    fetcher = SafeFetcher()

    async def _one(site_id: int) -> tuple[int, bool, str]:
        site = db.get_site(site_id)
        if not site:
            return site_id, False, "not found"
        async with sem:
            try:
                meta = await fetch_site_meta(fetcher, site["url"])
            except SiteUnitError as e:
                return site_id, False, e.code
            except Exception as e:  # noqa: BLE001
                log.warning("refresh %s failed: %s", site_id, e)
                return site_id, False, "error"
        fields: dict = {}
        if meta["logo"]:
            new_path = save_logo(meta["logo"], meta["ext"], url=site["url"])
            remove_logo(site.get("logo_path"))
            fields.update(logo_path=new_path, logo_source=meta["source"])
        if meta["title"]:
            fields["name"] = meta["title"]
        if meta["description"]:
            fields["description"] = meta["description"]
        db.update_site(site_id, fields)
        return site_id, True, ""

    results = await asyncio.gather(*[_one(i) for i in ids])
    await fetcher.aclose()
    updated = sum(1 for _, ok, _ in results if ok)
    return {"checked": len(ids), "updated": updated, "failed": len(ids) - updated,
            "results": [{"id": sid, "ok": ok, "error": err} for sid, ok, err in results]}


def classify_health(status_code: int | None, exc: Exception | None) -> str:
    if exc is None and status_code is not None:
        if status_code < 400:
            return "healthy"
        if status_code == 404:
            return "unreachable"
        return "error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return "unreachable"
    return "error"


async def check_health(ids: list[int] | None = None) -> dict:
    if not ids:
        sites = db.list_sites(archived=False)
        ids = [s["id"] for s in sites]
    sem = asyncio.Semaphore(settings.health_concurrency)
    fetcher = SafeFetcher()

    async def _one(site_id: int) -> dict:
        site = db.get_site(site_id)
        if not site:
            return {"id": site_id, "status": "error", "http_status": None}
        status_code: int | None = None
        exc: Exception | None = None
        async with sem:
            try:
                r = await fetcher.fetch(site["url"], max_bytes=1)
                status_code = r.status_code
            except SiteUnitError as e:
                exc = e
            except Exception as e:  # noqa: BLE001
                exc = e
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        klass = classify_health(status_code, exc if not isinstance(exc, SiteUnitError) else None)
        db.set_health(site_id, klass, status_code, now)
        return {"id": site_id, "status": klass, "http_status": status_code}

    results = await asyncio.gather(*[_one(i) for i in ids])
    await fetcher.aclose()
    return {"checked": len(ids), "results": results}
