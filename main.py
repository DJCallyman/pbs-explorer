from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routers import admin, atc_codes, health, items, organisations, reports, restrictions, schedules
from config import get_settings
from logging_config import setup_logging
from web.routes import router as web_router

logger = logging.getLogger(__name__)


def _is_web_request(request: Request) -> bool:
    """Heuristic: if the path starts with /web/ or Accept prefers HTML, treat as web."""
    if request.url.path.startswith("/web"):
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(title="PBS Explorer", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.allow_origins,
        allow_credentials=settings.server.allow_credentials,
        allow_methods=settings.server.allow_methods,
        allow_headers=settings.server.allow_headers,
    )

    # --------------- Exception handlers ---------------

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if _is_web_request(request):
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(
                directory=str(Path(__file__).resolve().parent / "web" / "templates")
            )
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "status_code": exc.status_code, "detail": exc.detail},
                status_code=exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        if _is_web_request(request):
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(
                directory=str(Path(__file__).resolve().parent / "web" / "templates")
            )
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "status_code": 500, "detail": "Internal server error"},
                status_code=500,
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # --------------- Routers ---------------

    app.include_router(items.router)
    app.include_router(restrictions.router)
    app.include_router(atc_codes.router)
    app.include_router(organisations.router)
    app.include_router(schedules.router)
    app.include_router(reports.router)
    app.include_router(admin.router)
    app.include_router(health.router)

    app.include_router(web_router)

    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()
