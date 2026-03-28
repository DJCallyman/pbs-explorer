from __future__ import annotations

import asyncio
import base64
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from urllib.parse import urlparse

from api.routers import admin, atc_codes, health, items, organisations, reports, restrictions, schedules
from config import get_settings
from db.base import Base
from db.models import MedicineStatusEntry, SavedReport, WebSession, WebUser
from db.session import get_session
from logging_config import setup_logging
from services.auth_store import has_users as auth_store_has_users, verify_any_user
from services.auth_rate_limiter import auth_rate_limiter
from services.saved_reports import validate_csv_access_token
from services.scheduler import app_scheduler
from services.session_store import get_session as get_web_session
from web.admin_web_routes import router as admin_web_router
from web.auth_routes import router as auth_router
from web.browse_routes import router as browse_router
from web.report_routes import router as report_router
from web.saved_report_routes import router as saved_report_router
from web.search_routes import router as search_router

logger = logging.getLogger(__name__)
SESSION_COOKIE_NAME = "pbs_explorer_session"


def _ensure_search_support_indexes() -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_indication_episodicity ON indication (episodicity)",
        "CREATE INDEX IF NOT EXISTS ix_item_restriction_pbs_schedule ON item_restriction_relationships (pbs_code, schedule_code)",
        "CREATE INDEX IF NOT EXISTS ix_item_restriction_schedule_pbs ON item_restriction_relationships (schedule_code, pbs_code)",
        "CREATE INDEX IF NOT EXISTS ix_restriction_prescribing_schedule_res ON restriction_prescribing_text_relationships (schedule_code, res_code)",
    ]
    with get_session() as session:
        for statement in statements:
            session.execute(text(statement))
        session.commit()


def _ensure_app_support_tables() -> None:
    import db.session as session_module

    session_module.init_engine()
    Base.metadata.create_all(
        bind=session_module._engine,
        tables=[
            MedicineStatusEntry.__table__,
            WebUser.__table__,
            WebSession.__table__,
            SavedReport.__table__,
        ],
    )
@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_app_support_tables()
    _ensure_search_support_indexes()
    await app_scheduler.start()
    app.state.app_scheduler = app_scheduler
    try:
        yield
    finally:
        await app_scheduler.stop()


def _is_web_request(request: Request) -> bool:
    """Heuristic: if the path starts with /web/ or Accept prefers HTML, treat as web."""
    if request.url.path.startswith("/api/") or request.url.path.startswith("/static/"):
        return False
    if request.url.path.startswith("/web"):
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _request_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded_proto.lower() == "https"


def _same_origin_web_write(request: Request) -> bool:
    target_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
    for header_name in ("origin", "referer"):
        raw = request.headers.get(header_name, "").strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            return False
        return f"{parsed.scheme}://{parsed.netloc}" == target_origin
    return False


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_key(request: Request, username: str) -> str:
    return f"{_client_identifier(request).lower()}::{username.strip().lower()}"


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(
        title="PBS Explorer",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.server.enable_docs else None,
        redoc_url="/redoc" if settings.server.enable_docs else None,
        openapi_url="/openapi.json" if settings.server.enable_docs else None,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.server.trusted_hosts or ["127.0.0.1", "localhost", "::1"],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.allow_origins,
        allow_credentials=settings.server.allow_credentials,
        allow_methods=settings.server.allow_methods,
        allow_headers=settings.server.allow_headers,
    )

    web_auth_enabled = bool(
        (settings.server.web_username and settings.server.web_password)
        or auth_store_has_users()
    )

    def _basic_auth_response() -> Response:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": 'Basic realm="PBS Explorer API"'},
        )

    def _is_exempt_path(path: str) -> bool:
        return (
            path.startswith("/api/v1/health")
            or path.startswith("/static/")
            or path == "/login"
            or path == "/logout"
        )

    def _has_valid_saved_report_token(request: Request) -> bool:
        path = request.url.path
        if not path.startswith("/web/saved-reports/") or not path.endswith(".csv"):
            return False
        slug = path.rsplit("/", 1)[-1][:-4]
        token = request.query_params.get("access_token", "")
        return validate_csv_access_token(slug, token)

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        request.state.web_auth_user = ""
        request.state.web_auth_role = ""
        request.state.web_auth_source = ""
        request.state.enable_psd = settings.server.enable_psd

        if web_auth_enabled and not _is_exempt_path(request.url.path) and not _has_valid_saved_report_token(request):
            browser_request = _is_web_request(request)
            session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
            session = get_web_session(session_token) if session_token else None

            if session:
                request.state.web_auth_user = session.username
                request.state.web_auth_role = session.role
                request.state.web_auth_source = session.source
            elif not browser_request:
                auth_header = request.headers.get("authorization", "")
                if not auth_header.startswith("Basic "):
                    return _basic_auth_response()
                try:
                    decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                    username, password = decoded.split(":", 1)
                except Exception:
                    return _basic_auth_response()

                rate_key = _rate_limit_key(request, username)
                retry_after = auth_rate_limiter.check(rate_key)
                if retry_after:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many authentication attempts. Try again later."},
                        headers={"Retry-After": str(retry_after)},
                    )

                user = verify_any_user(
                    username,
                    password,
                    settings.server.web_username,
                    settings.server.web_password,
                )
                if not user:
                    auth_rate_limiter.record_failure(rate_key)
                    return _basic_auth_response()
                auth_rate_limiter.clear(rate_key)
                request.state.web_auth_user = user.username
                request.state.web_auth_role = user.role
                request.state.web_auth_source = user.source
            else:
                next_target = quote(request.url.path + (f"?{request.url.query}" if request.url.query else ""), safe="/?=&")
                return RedirectResponse(url=f"/login?next={next_target}", status_code=303)

        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and _is_web_request(request)
            and getattr(request.state, "web_auth_user", "")
            and not request.url.path.startswith("/api/")
            and request.url.path not in {"/login"}
        ):
            if not _same_origin_web_write(request):
                return JSONResponse(status_code=403, content={"detail": "Cross-site form submission blocked"})

        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

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

    app.include_router(auth_router)
    app.include_router(admin_web_router)
    app.include_router(browse_router)
    app.include_router(report_router)
    app.include_router(saved_report_router)
    app.include_router(search_router)

    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()
