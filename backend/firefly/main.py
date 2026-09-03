"""
FastAPI 應用 / FastAPI application(文件 03 API Gateway)。

- 統一錯誤格式(文件 06)/ uniform error format (doc 06)
- 開放資料 GET 全域 CORS;寫入端點僅白名單來源(文件 06)/ open-data GET is CORS-open; write endpoints allowlisted
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from . import __version__
from .api.open_data import router as open_router
from .api.routes import router as v1_router
from .bots.line import router as line_router
from .config import get_config


def create_app() -> FastAPI:
    app = FastAPI(title="螢火 Firefly API", version=__version__, license_info={"name": "AGPL-3.0"})
    cfg = get_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors.open_data_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(v1_router)
    app.include_router(open_router)
    app.include_router(line_router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        d = exc.detail
        if isinstance(d, dict) and "code" in d:
            body = {"error": d}
        else:
            body = {"error": {"code": "http_error", "message_zh": str(d), "message_en": str(d)}}
        return JSONResponse(status_code=exc.status_code, content=body, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message_zh": "請求格式錯誤", "message_en": "Invalid request", "details": exc.errors()}})

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "version": __version__, "config_version": cfg.version}

    return app


app = create_app()
