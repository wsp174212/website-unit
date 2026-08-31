"""Unified error model for the SiteUnit API.

Every business error raises :class:`SiteUnitError` carrying a stable ``code``
and a human-friendly message. A FastAPI exception handler turns it into::

    {"error": {"code": "...", "message": "..."}}

so the frontend can branch on ``code`` instead of parsing exception strings.
"""

from __future__ import annotations

from enum import Enum

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(str, Enum):
    # input / url
    EMPTY_URL = "EMPTY_URL"
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
    # site lifecycle
    SITE_NOT_FOUND = "SITE_NOT_FOUND"
    SITE_ALREADY_EXISTS = "SITE_ALREADY_EXISTS"
    # fetching
    SSRF_BLOCKED = "SSRF_BLOCKED"
    LOGO_FETCH_FAILED = "LOGO_FETCH_FAILED"
    INVALID_LOGO = "INVALID_LOGO"
    FETCH_TIMEOUT = "FETCH_TIMEOUT"
    # io
    IMPORT_FAILED = "IMPORT_FAILED"
    INVALID_ARCHIVE = "INVALID_ARCHIVE"
    BACKUP_FAILED = "BACKUP_FAILED"
    # generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class SiteUnitError(Exception):
    def __init__(self, code: ErrorCode | str, message: str, status_code: int = 400):
        self.code = code.value if isinstance(code, Enum) else str(code)
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def raise_not_found(msg: str = "未找到资源") -> None:
    raise SiteUnitError(ErrorCode.NOT_FOUND, msg, 404)


def raise_conflict(code: ErrorCode, msg: str) -> None:
    raise SiteUnitError(code, msg, 409)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_handlers(app) -> None:
    @app.exception_handler(SiteUnitError)
    async def _siteunit_error(_: Request, exc: SiteUnitError):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        # Surface the first failing field as a friendly message; keep code fixed.
        msg = "请求参数有误"
        if exc.errors():
            e = exc.errors()[0]
            loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body",))
            msg = f"{loc or '字段'}：{e.get('msg', msg)}"
        return JSONResponse(status_code=422, content=_error_body(ErrorCode.VALIDATION_ERROR.value, msg))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        # Preserve FastAPI's HTTPException semantics (404 etc.) in our envelope.
        detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
        code = ErrorCode.NOT_FOUND.value if exc.status_code == 404 else ErrorCode.INTERNAL_ERROR.value
        return JSONResponse(status_code=exc.status_code, content=_error_body(code, detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):  # noqa: BLE001
        from .config import settings
        import logging
        logging.getLogger("siteunit").exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content=_error_body(ErrorCode.INTERNAL_ERROR.value, "服务器内部错误"),
        )
