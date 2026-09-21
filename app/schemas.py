"""Pydantic request/response models.

Response models keep raw SQLite rows out of the API surface and let FastAPI
generate accurate OpenAPI docs. ``serialize_site`` maps a db row (which uses
``group_name``/``logo_path``) to the ``SiteOut`` shape (``group``/``logo_url``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class SiteBase(BaseModel):
    url: str
    name: str = ""
    description: str = ""
    group: str = Field(default="", max_length=80)
    tags: list[str] = Field(default_factory=list)


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    url: str | None = None
    name: str | None = None
    description: str | None = None
    group: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = None
    favorite: bool | None = None
    pinned: bool | None = None
    archived: bool | None = None
    refetch_metadata: bool = False


class SiteOut(BaseModel):
    id: int
    url: str
    name: str
    description: str
    group: str
    tags: list[str] = Field(default_factory=list)
    logo_url: str | None = None
    logo_source: str = ""
    favorite: bool = False
    pinned: bool = False
    sort_order: int = 0
    visit_count: int = 0
    last_visited_at: str | None = None
    status: str = "unknown"
    http_status: int | None = None
    last_checked_at: str | None = None
    archived: bool = False
    created_at: str = ""
    updated_at: str = ""


def serialize_site(row: dict) -> dict:
    """Convert a db row dict to the SiteOut response shape."""
    return {
        "id": row["id"],
        "url": row["url"],
        "name": row["name"],
        "description": row["description"],
        "group": row["group_name"],
        "tags": row.get("tags", []),
        "logo_url": _logo_url(row.get("logo_path")),
        "logo_source": row.get("logo_source", ""),
        "favorite": bool(row.get("favorite", 0)),
        "pinned": bool(row.get("pinned", 0)),
        "sort_order": row.get("sort_order", 0),
        "visit_count": row.get("visit_count", 0),
        "last_visited_at": row.get("last_visited_at"),
        "status": row.get("status", "unknown"),
        "http_status": row.get("http_status"),
        "last_checked_at": row.get("last_checked_at"),
        "archived": bool(row.get("archived", 0)),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }


def _logo_url(path: str | None) -> str | None:
    from .logos import logo_url_for
    return logo_url_for(path)


# ---------- reorder ----------

class ReorderItem(BaseModel):
    site_id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


# ---------- bulk ----------

BulkActionKind = Literal[
    "delete", "move_group", "add_tag", "replace_tags", "archive", "unarchive", "refresh_metadata"
]


class BulkActionRequest(BaseModel):
    action: BulkActionKind
    ids: list[int]
    group: str | None = None
    tags: list[str] | None = None


class BulkResult(BaseModel):
    action: str
    affected: int
    message: str


# ---------- tags / groups ----------

class TagOut(BaseModel):
    id: int
    name: str
    count: int


class GroupOut(BaseModel):
    name: str
    count: int


class TagRename(BaseModel):
    name: str


# ---------- statistics ----------

class DailyVisit(BaseModel):
    date: str
    count: int


class TopSiteVisit(BaseModel):
    site_id: int
    name: str
    url: str
    logo_url: str | None = None
    visits: int


class VisitGroup(BaseModel):
    name: str
    count: int


class StatsOverview(BaseModel):
    days: int
    total_visits: int
    daily: list[DailyVisit]
    top_sites: list[TopSiteVisit]
    groups: list[VisitGroup]


# ---------- visit ----------

class VisitResponse(BaseModel):
    id: int
    visit_count: int
    last_visited_at: str | None


# ---------- health ----------

class HealthCheckRequest(BaseModel):
    ids: list[int] | None = None


class HealthCheckResult(BaseModel):
    checked: int
    results: list[dict]


# ---------- import / export ----------

class ExportData(BaseModel):
    version: int = 1
    exported_at: str
    sites: list[dict]
    groups: list[dict]
    tags: list[dict]


class ImportPreview(BaseModel):
    total: int
    added: int
    duplicates: int
    invalid: int
    errors: list[str]


class ImportResult(ImportPreview):
    mode: str


class ImportRequest(BaseModel):
    mode: Literal["merge", "replace"] = "merge"
    data: ExportData | None = None


class BackupInfo(BaseModel):
    path: str
    size: int
    created_at: str
