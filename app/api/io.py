"""Import / export / backup routes.

- JSON export/import (merge or replace) with schema version
- CSV export/import
- Browser bookmarks HTML import (Chrome / Edge / Firefox)
- Backup (zip of sites.db + logos/) and restore (path-traversal-safe)
"""

from __future__ import annotations

import csv
import io as _io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from .. import db
from ..config import settings
from ..errors import ErrorCode, SiteUnitError
from ..schemas import ExportData, ImportPreview, ImportResult, serialize_site
from ..urlnorm import normalize_url, canonical_key

router = APIRouter(prefix="/api/io", tags=["import-export"])


# ---------- export ----------

def _export_data() -> dict:
    sites = db.list_sites(archived=None)  # all, regardless of archived
    groups = db.list_groups()
    tags = db.all_tags()
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sites": [serialize_site(s) for s in sites],
        "groups": groups,
        "tags": tags,
    }


@router.get("/export.json")
async def export_json():
    data = _export_data()
    payload = _io.BytesIO(__import__("json").dumps(data, ensure_ascii=False).encode("utf-8"))
    return StreamingResponse(
        payload, media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="siteunit-export.json"'},
    )


@router.get("/export.csv")
async def export_csv():
    sites = db.list_sites(archived=None)
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(["url", "name", "description", "group", "tags"])
    for s in sites:
        row = serialize_site(s)
        w.writerow([row["url"], row["name"], row["description"], row["group"], ";".join(row["tags"])])
    data = buf.getvalue().encode("utf-8-sig")  # utf-8-sig so Excel reads CJK
    return StreamingResponse(
        _io.BytesIO(data), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="siteunit-export.csv"'},
    )


# ---------- shared import core ----------

def _import_sites(rows: list[dict], mode: str) -> ImportResult:
    """rows: [{url,name,description,group,tags}]. Apply import, return counts."""
    added = dup = invalid = 0
    errors: list[str] = []
    if mode == "replace":
        # back up current data before wiping
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        try:
            db.backup_db(settings.backup_dir / f"pre-import-{stamp}.db")
        except Exception:
            pass
        with db._connect() as conn:  # noqa: SLF001
            conn.execute("DELETE FROM site_tags")
            conn.execute("DELETE FROM sites")
            conn.execute("DELETE FROM tags")
    for i, r in enumerate(rows):
        try:
            url = normalize_url(r.get("url", ""))
        except SiteUnitError:
            invalid += 1
            errors.append(f"row {i}: invalid url {r.get('url')!r}")
            continue
        if db.get_by_normalized_url(url):
            dup += 1
            continue
        try:
            db.insert_site(
                name=(r.get("name") or url).strip(),
                url=url,
                description=(r.get("description") or "").strip(),
                group_name=(r.get("group") or r.get("group_name") or "").strip(),
                logo_path="", logo_source="",
                tags=[t for t in (r.get("tags") or []) if t],
            )
            added += 1
        except Exception as e:  # noqa: BLE001
            invalid += 1
            errors.append(f"row {i}: {e}")
    return ImportResult(mode=mode, total=len(rows), added=added,
                        duplicates=dup, invalid=invalid, errors=errors)


def _preview_rows(rows: list[dict]) -> ImportPreview:
    dup = invalid = 0
    errors: list[str] = []
    for i, r in enumerate(rows):
        try:
            url = normalize_url(r.get("url", ""))
        except SiteUnitError:
            invalid += 1
            errors.append(f"row {i}: invalid url")
            continue
        if db.get_by_normalized_url(url):
            dup += 1
    return ImportPreview(total=len(rows), added=len(rows) - dup - invalid,
                         duplicates=dup, invalid=invalid, errors=errors)


# ---------- json import ----------

@router.post("/import/preview/json", response_model=ImportPreview)
async def preview_json(data: ExportData):
    return _preview_rows(data.sites)


@router.post("/import/json", response_model=ImportResult)
async def import_json(data: ExportData, mode: str = Query("merge")):
    return _import_sites(data.sites, mode)


# ---------- csv import ----------

def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(_io.StringIO(text))
    return [
        {"url": r.get("url", ""), "name": r.get("name", ""),
         "description": r.get("description", ""), "group": r.get("group", ""),
         "tags": [t for t in (r.get("tags") or "").split(";") if t]}
        for r in reader
    ]


@router.post("/import/csv", response_model=ImportResult)
async def import_csv(file: UploadFile = File(...), mode: str = Query("merge")):
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    return _import_sites(_parse_csv(raw), mode)


# ---------- bookmarks html import ----------

def _parse_bookmarks(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or not href.startswith(("http://", "https://")):
            continue
        # nearest enclosing folder name
        folder = "未分类"
        for parent in a.parents:
            h3 = parent.find_previous_sibling("h3") if hasattr(parent, "find_previous_sibling") else None
            if h3 and h3.get_text(strip=True):
                folder = h3.get_text(strip=True)
                break
        rows.append({
            "url": href, "name": a.get_text(strip=True)[:200],
            "description": "", "group": folder, "tags": [],
        })
    return rows


@router.post("/import/preview/bookmarks", response_model=ImportPreview)
async def preview_bookmarks(file: UploadFile = File(...)):
    html = (await file.read()).decode("utf-8", errors="replace")
    return _preview_rows(_parse_bookmarks(html))


@router.post("/import/bookmarks", response_model=ImportResult)
async def import_bookmarks(file: UploadFile = File(...), mode: str = Query("merge")):
    html = (await file.read()).decode("utf-8", errors="replace")
    return _import_sites(_parse_bookmarks(html), mode)


# ---------- backup / restore ----------

@router.get("/backup")
async def backup():
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # checkpoint WAL into the main db file before copying
        db.backup_db(settings.data_dir / "_backup_tmp.db")
        try:
            zf.write(settings.data_dir / "_backup_tmp.db", "sites.db")
        finally:
            (settings.data_dir / "_backup_tmp.db").unlink(missing_ok=True)
        if settings.logo_dir.exists():
            for p in settings.logo_dir.iterdir():
                if p.is_file():
                    zf.write(p, f"logos/{p.name}")
        zf.writestr("manifest.json", __import__("json").dumps({
            "version": 1, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": "siteunit",
        }))
    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="siteunit-backup-{stamp}.zip"'},
    )


@router.post("/restore")
async def restore(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        zf = zipfile.ZipFile(_io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise SiteUnitError(ErrorCode.INVALID_ARCHIVE, "不是有效的 zip 文件", 422)

    # path traversal guard
    for name in zf.namelist():
        norm = name.replace("\\", "/")
        if norm.startswith("/") or ".." in norm.split("/"):
            raise SiteUnitError(ErrorCode.INVALID_ARCHIVE, f"压缩包含非法路径：{name}", 422)
        if not (norm == "sites.db" or norm == "manifest.json" or norm.startswith("logos/")):
            raise SiteUnitError(ErrorCode.INVALID_ARCHIVE, f"压缩包含未知条目：{name}", 422)

    # back up current data before replacing
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        db.backup_db(settings.backup_dir / f"pre-restore-{stamp}.db")
    except Exception:
        pass

    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    # clear existing logos to avoid stale leftovers
    for p in settings.logo_dir.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)

    db_path = settings.db_path
    # release WAL into the main file and clear sidecars so the overwrite is clean
    with db._connect() as conn:  # noqa: SLF001
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for suffix in ("-wal", "-shm"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
    for name in zf.namelist():
        norm = name.replace("\\", "/")
        if norm == "sites.db":
            db_path.write_bytes(zf.read(name))
        elif norm.startswith("logos/"):
            fn = norm.removeprefix("logos/")
            if fn:
                (settings.logo_dir / fn).write_bytes(zf.read(name))
    # run migrations on the restored db (may be older schema)
    db.init_db()
    return {"restored": True, "message": "已恢复，请刷新页面"}
