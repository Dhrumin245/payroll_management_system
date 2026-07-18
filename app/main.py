"""
FastAPI app instance and top-level wiring.

Routers get registered here as each phase builds them.
"""
import logging

from fastapi import Depends, FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.dependencies import get_current_user, get_db, limiter
from app.exceptions import NotAuthenticatedException, NotAuthorizedException
from app.flash import flash
from app.models import User
from app.routers import attendance, auth, employees, payroll, portal, leaves, variable_pay, settings as settings_router, analytics, users as users_router
from app.services.dashboard_service import get_dashboard_data, get_payroll_trend, get_compensation_breakdown, get_headcount_trend
from app.templating import render

logger = logging.getLogger("app")

app = FastAPI(title="Payroll Management System")

# --- Session middleware -------------------------------------------------------
# Starlette's SessionMiddleware is what stands in for Flask-Login here: a
# signed, HttpOnly cookie holding session data (user_id, login_time,
# last_activity, csrf_token, _flashes). See app/dependencies.py for the auth
# logic built on top of it.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE_SECONDS,
    https_only=settings.ENVIRONMENT == "production",
    same_site="lax",
)

# --- Rate limiting (slowapi — a Flask-Limiter-style limiter for FastAPI) ------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# --- Auth redirect handler -----------------------------------------------------
@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    """App Flow §4.1: redirect to /login?next=<path> with a flash message."""
    flash(request, "Please log in to continue.", "info")
    return RedirectResponse(
        url=f"/login?next={request.url.path}", status_code=status.HTTP_303_SEE_OTHER
    )


@app.exception_handler(NotAuthorizedException)
async def not_authorized_handler(request: Request, exc: NotAuthorizedException):
    """Renders the 403 Access Denied page for role-guard failures."""
    return render(request, "errors/403.html", status_code=403)


# --- Styled error pages (App Flow §4.2-4.3) -----------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return render(request, "errors/404.html", status_code=404)
    if exc.status_code == 403:
        return render(request, "errors/403.html", status_code=403)
    # Any other HTTP exception keeps FastAPI's default behavior.
    return await default_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    App Flow §4.3: generic message, no stack trace shown to the user --
    logged server-side only.
    """
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return render(request, "errors/500.html", status_code=500)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- Routers -------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(payroll.router)
app.include_router(portal.router)
app.include_router(leaves.router)
app.include_router(variable_pay.router)
app.include_router(settings_router.router)
app.include_router(analytics.router)
app.include_router(users_router.router)


# --- Dashboard ------------------------------------------------------------
@app.get("/dashboard")
def dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return render(
        request,
        "dashboard.html",
        {
            "user": user,
            "active_nav": "dashboard",
            "dummy": get_dashboard_data(db),
            "payroll_trend": get_payroll_trend(db),
            "comp_breakdown": get_compensation_breakdown(db),
            "headcount_trend": get_headcount_trend(db),
        },
    )


@app.get("/")
def read_root():
    """Root just forwards to the dashboard, which itself enforces login."""
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
