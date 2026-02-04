from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import admin, atc_codes, health, items, organisations, reports, restrictions, schedules
from config import get_settings
from logging_config import setup_logging
from web.routes import router as web_router


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
