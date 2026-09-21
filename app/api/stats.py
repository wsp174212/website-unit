"""Statistics API: visit aggregation for the dashboard."""

from __future__ import annotations

from enum import IntEnum

from fastapi import APIRouter, Query

from .. import db
from ..schemas import StatsOverview

router = APIRouter(prefix="/api/stats", tags=["stats"])


class StatsWindow(IntEnum):
    SEVEN_DAYS = 7
    THIRTY_DAYS = 30
    NINETY_DAYS = 90


@router.get("/overview", response_model=StatsOverview)
async def get_overview(
    days: StatsWindow = Query(StatsWindow.THIRTY_DAYS, description="Statistics window in days"),
) -> StatsOverview:
    return StatsOverview(**db.stats_overview(int(days)))
