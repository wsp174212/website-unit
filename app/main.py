"""SiteUnit — personal website launcher backend (FastAPI + SQLite)."""

import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import db
from .db import LOGO_DIR
from .logos import fetch_site_meta, normalize_url

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="SiteUnit", lifespan=lifespan)


# ---------- schemas ----------

class SiteCreate(BaseModel):
    url: str
    name: str = ""
    description: str = ""
    grp: str = Field(default="", max_length=40)


class SiteUpdate(BaseModel):
    url: str | None = None
    name: str | None = None
    description: str | None = None
    grp: str | None = Field(default=None, max_length=40)
    refetch_logo: bool = False


# ---------- helpers ----------

def _with_logo_url(site: dict) -> dict:
    out = dict(site)
    out["logo_url"] = f"/logos/{out['logo']}" if out.get("logo") else None
    return out


def _save_logo(content: bytes, ext: str) -> str:
    filename = f"{uuid.uuid4().hex}.{ext}"
    (LOGO_DIR / filename).write_bytes(content)
    return filename


def _remove_logo_file(filename: str | None) -> None:
    if not filename:
        return
    # filename comes from our own records; be defensive anyway.
    if not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]+", filename):
        return
    try:
        (LOGO_DIR / filename).unlink(missing_ok=True)
    except OSError:
        pass


async def _fetch_logo_for(url: str) -> tuple[bytes, str] | None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12.0), follow_redirects=True, verify=False
    ) as client:
        meta = await fetch_site_meta(client, url)
    if meta["logo"]:
        return meta["logo"], meta["ext"]
    return None


async def _fetch_meta_for(url: str) -> dict:
    # verify=False: many hobby/self-hosted sites have broken TLS; we only read
    # public pages and store public icons, so the risk is acceptable locally.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(12.0), follow_redirects=True, verify=False
    ) as client:
        return await fetch_site_meta(client, url)


# ---------- API ----------

@app.get("/api/sites")
async def list_sites():
    return [_with_logo_url(s) for s in db.list_sites()]


@app.post("/api/sites", status_code=201)
async def create_site(payload: SiteCreate):
    try:
        url = normalize_url(payload.url)
    except ValueError as e:
        raise HTTPException(400, str(e))

    name = payload.name.strip()
    title = ""
    logo_filename = ""
    if url.startswith(("http://", "https://")):
        meta = await _fetch_meta_for(url)
        title = meta["title"]
        if meta["logo"]:
            logo_filename = _save_logo(meta["logo"], meta["ext"])

    if not name:
        name = title or url

    site = db.insert_site(
        name=name,
        url=url,
        description=payload.description.strip(),
        grp=payload.grp.strip(),
        logo=logo_filename,
    )
    return _with_logo_url(site)


@app.put("/api/sites/{site_id}")
async def update_site(site_id: int, payload: SiteUpdate):
    site = db.get_site(site_id)
    if site is None:
        raise HTTPException(404, "站点不存在")

    fields: dict = {}
    refetch = payload.refetch_logo
    if payload.url is not None and payload.url.strip() != site["url"]:
        try:
            fields["url"] = normalize_url(payload.url)
        except ValueError as e:
            raise HTTPException(400, str(e))
        refetch = True
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.description is not None:
        fields["description"] = payload.description.strip()
    if payload.grp is not None:
        fields["grp"] = payload.grp.strip()

    if refetch and fields.get("url", site["url"]).startswith(("http://", "https://")):
        got = await _fetch_logo_for(fields.get("url", site["url"]))
        if got:
            new_file = _save_logo(*got)
            _remove_logo_file(site["logo"])
            fields["logo"] = new_file

    updated = db.update_site(site_id, fields)
    return _with_logo_url(updated)


@app.post("/api/sites/{site_id}/refetch-logo")
async def refetch_logo(site_id: int):
    site = db.get_site(site_id)
    if site is None:
        raise HTTPException(404, "站点不存在")
    got = await _fetch_logo_for(site["url"])
    if not got:
        raise HTTPException(422, "无法获取该站点的 logo，可稍后重试或检查站点是否可访问")
    new_file = _save_logo(*got)
    _remove_logo_file(site["logo"])
    updated = db.update_site(site_id, {"logo": new_file})
    return _with_logo_url(updated)


@app.delete("/api/sites/{site_id}", status_code=204)
async def delete_site(site_id: int):
    logo = db.delete_site(site_id)
    if logo is None:
        raise HTTPException(404, "站点不存在")
    _remove_logo_file(logo)
    return None


# ---------- frontend ----------

LOGO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/logos", StaticFiles(directory=LOGO_DIR), name="logos")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
