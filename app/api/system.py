"""System routes: tags, groups, maintenance, db info."""

from __future__ import annotations

from fastapi import APIRouter

from .. import db, logos
from ..schemas import GroupOut, TagOut

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/tags", response_model=list[TagOut])
async def tags():
    return db.all_tags()


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: int):
    with db._connect() as conn:  # noqa: SLF001
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    return None


@router.get("/groups", response_model=list[GroupOut])
async def groups():
    return db.list_groups()


@router.post("/system/gc-logos")
async def gc_logos():
    removed = logos.garbage_collect(db.referenced_logos())
    return {"removed": removed}


@router.get("/system/db-info")
async def db_info():
    return db.db_info()
