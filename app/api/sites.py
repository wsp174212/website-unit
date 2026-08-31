"""Sites API: CRUD, visit, refetch, reorder, bulk, search."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import db, services
from ..errors import ErrorCode, SiteUnitError
from ..schemas import (
    BulkActionRequest, BulkResult, ReorderRequest, SiteCreate,
    SiteOut, SiteUpdate, VisitResponse, serialize_site,
)

router = APIRouter(prefix="/api/sites", tags=["sites"])

_TRUE = {"1", "true", "yes"}


def _parse_query(q: str | None) -> dict:
    """Token-aware search: ``group:AI tag:coding fav:true pinned:true``."""
    if not q:
        return {}
    out: dict = {"text": [], "group": None, "tag": None, "favorite": False, "pinned": False}
    for tok in q.split():
        low = tok.lower()
        if low.startswith("group:"):
            out["group"] = tok[6:] or None
        elif low.startswith("tag:"):
            out["tag"] = tok[4:] or None
        elif low.startswith("fav:"):
            out["favorite"] = low.split(":", 1)[1] in _TRUE
        elif low.startswith("pinned:"):
            out["pinned"] = low.split(":", 1)[1] in _TRUE
        else:
            out["text"].append(tok)
    out["text"] = " ".join(out.pop("text")) or None
    return out


@router.get("", response_model=list[SiteOut])
async def list_sites(
    order: str = Query("custom"),
    archived: bool | None = Query(False),
    q: str | None = Query(None),
    group: str | None = Query(None),
    tag: str | None = Query(None),
    favorite: bool | None = Query(None),
    pinned: bool | None = Query(None),
):
    parsed = _parse_query(q)
    filt = dict(
        order=order,
        archived=archived,
        text=parsed.get("text"),
        group=parsed.get("group") or group,
        tag=parsed.get("tag") or tag,
        favorite=parsed.get("favorite") or favorite,
        pinned=parsed.get("pinned") or pinned,
    )
    return [serialize_site(s) for s in db.list_sites(**filt)]


@router.post("", response_model=SiteOut, status_code=201)
async def create_site(payload: SiteCreate):
    return await services.create_site(payload)


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: int):
    site = db.get_site(site_id)
    if site is None:
        raise SiteUnitError(ErrorCode.SITE_NOT_FOUND, "站点不存在", 404)
    return serialize_site(site)


@router.put("/{site_id}", response_model=SiteOut)
async def update_site(site_id: int, payload: SiteUpdate):
    return await services.update_site_record(site_id, payload)


@router.delete("/{site_id}", status_code=204)
async def delete_site(site_id: int):
    from ..logos import remove_logo
    site = db.delete_site(site_id)
    if site is None:
        raise SiteUnitError(ErrorCode.SITE_NOT_FOUND, "站点不存在", 404)
    remove_logo(site.get("logo_path"))
    return None


@router.post("/{site_id}/visit", response_model=VisitResponse)
async def visit_site(site_id: int):
    if not db.visit_site(site_id):
        raise SiteUnitError(ErrorCode.SITE_NOT_FOUND, "站点不存在", 404)
    site = db.get_site(site_id)
    return VisitResponse(id=site_id, visit_count=site["visit_count"], last_visited_at=site["last_visited_at"])


@router.post("/{site_id}/refetch-logo", response_model=SiteOut)
async def refetch_logo(site_id: int):
    return await services.refetch_logo(site_id)


@router.post("/reorder")
async def reorder(payload: ReorderRequest):
    db.reorder([(i.site_id, i.sort_order) for i in payload.items])
    return {"updated": len(payload.items)}


@router.post("/bulk", response_model=BulkResult)
async def bulk_action(payload: BulkActionRequest):
    if not payload.ids:
        return BulkResult(action=payload.action, affected=0, message="无选中站点")
    ids = payload.ids
    if payload.action == "delete":
        from ..logos import remove_logo
        affected = 0
        for sid in ids:
            site = db.delete_site(sid)
            if site is not None:
                remove_logo(site.get("logo_path"))
                affected += 1
        return BulkResult(action="delete", affected=affected, message=f"已删除 {affected} 个站点")
    if payload.action == "move_group":
        for sid in ids:
            db.update_site(sid, {"group_name": (payload.group or "")})
        return BulkResult(action="move_group", affected=len(ids), message=f"已移动 {len(ids)} 个站点到「{payload.group or '未分类'}」")
    if payload.action in ("add_tag", "replace_tags"):
        if not payload.tags:
            raise SiteUnitError(ErrorCode.VALIDATION_ERROR, "缺少 tags 参数", 422)
        for sid in ids:
            site = db.get_site(sid)
            if not site:
                continue
            if payload.action == "add_tag":
                new_tags = list({*site["tags"], *payload.tags})
            else:
                new_tags = list(payload.tags)
            db.update_site(sid, {"tags": new_tags})
        return BulkResult(action=payload.action, affected=len(ids), message=f"已更新 {len(ids)} 个站点的标签")
    if payload.action in ("archive", "unarchive"):
        val = 1 if payload.action == "archive" else 0
        for sid in ids:
            db.update_site(sid, {"archived": val})
        return BulkResult(action=payload.action, affected=len(ids), message="已归档" if val else "已恢复")
    if payload.action == "refresh_metadata":
        res = await services.refresh_metadata_bulk(ids)
        return BulkResult(action="refresh_metadata", affected=res["updated"],
                          message=f"刷新完成：{res['updated']}/{res['checked']} 成功")
    raise SiteUnitError(ErrorCode.VALIDATION_ERROR, "未知操作", 422)
