from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from config import get_settings
from services.auth_store import verify_any_user
from services.auth_rate_limiter import auth_rate_limiter
from services.session_store import create_session, revoke_session

SESSION_COOKIE_NAME = "pbs_explorer_session"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(include_in_schema=False)


def _request_is_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded_proto.lower() == "https"


def _sanitize_next_path(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw.startswith("/") or raw.startswith("//"):
        return "/search"
    return raw


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_key(request: Request, username: str) -> str:
    return f"{_client_identifier(request).lower()}::{username.strip().lower()}"


@router.get("/")
def home(request: Request):
    return RedirectResponse(url="/search", status_code=307)


@router.get("/login")
def login_page(request: Request, next: str | None = None):
    if getattr(request.state, "web_auth_user", ""):
        return RedirectResponse(url=_sanitize_next_path(next), status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next_target": _sanitize_next_path(next),
            "error": request.query_params.get("error", ""),
        },
    )


@router.post("/login")
async def login_submit(request: Request):
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)

    username = str(parsed.get("username", [""])[0] or "").strip()
    password = str(parsed.get("password", [""])[0] or "")
    next_target = _sanitize_next_path(str(parsed.get("next", ["/search"])[0] or "/search"))
    rate_key = _rate_limit_key(request, username)

    retry_after = auth_rate_limiter.check(rate_key)
    if retry_after:
        return RedirectResponse(
            url="/login?"
            + urlencode(
                {
                    "error": f"Too many sign-in attempts. Please wait about {max((retry_after + 59) // 60, 1)} minute(s) and try again.",
                    "next": next_target,
                }
            ),
            status_code=303,
            headers={"Retry-After": str(retry_after)},
        )

    settings = get_settings()
    user = verify_any_user(
        username,
        password,
        settings.server.web_username,
        settings.server.web_password,
    )
    if not user:
        auth_rate_limiter.record_failure(rate_key)
        return RedirectResponse(
            url="/login?" + urlencode({"error": "Invalid username or password", "next": next_target}),
            status_code=303,
        )

    auth_rate_limiter.clear(rate_key)
    session = create_session(user.username, user.role, user.source)
    response = RedirectResponse(url=next_target, status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.session_id,
        httponly=True,
        samesite="lax",
        secure=_request_is_secure(request),
        path="/",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@router.post("/logout")
def logout(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if session_token:
        revoke_session(session_token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
