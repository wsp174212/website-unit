"""Health-check & maintenance routes."""

from __future__ import annotations

from fastapi import APIRouter

from .. import db, services
from ..schemas import HealthCheckRequest, HealthCheckResult, serialize_site

router = APIRouter(prefix="/api/health", tags=["health"])


@router.post("/check", response_model=HealthCheckResult)
async def check(payload: HealthCheckRequest):
    res = await services.check_health(payload.ids)
    return HealthCheckResult(checked=res["checked"], results=res["results"])


@router.get("/broken")
async def broken():
    sites = db.list_sites(archived=False, order="custom")
    broken = [s for s in sites if s["status"] in ("unreachable", "timeout", "error")]
    return [serialize_site(s) for s in broken]


@router.post("/refresh-metadata")
async def refresh_metadata(ids: list[int] = None):
    if not ids:
        sites = db.list_sites(archived=False)
        ids = [s["id"] for s in sites]
    return await services.refresh_metadata_bulk(ids)
