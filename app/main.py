"""SiteUnit — FastAPI application factory.

Wires together the routers, error handlers, static/logo mounts and the
lifespan that runs migrations on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api import health, io, sites, system
from .config import settings
from .errors import register_handlers

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def setup_logging() -> None:
    logger = logging.getLogger("siteunit")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    db.init_db()
    logging.getLogger("siteunit").info("SiteUnit ready on %s:%s", settings.host, settings.port)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="SiteUnit", version="2.0", lifespan=lifespan)
    register_handlers(app)

    app.include_router(sites.router)
    app.include_router(system.router)
    app.include_router(health.router)
    app.include_router(io.router)

    # logo dir must exist at import for StaticFiles; lifespan re-creates it.
    settings.logo_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/logos", StaticFiles(directory=settings.logo_dir), name="logos")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
