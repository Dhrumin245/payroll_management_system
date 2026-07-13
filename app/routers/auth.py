from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db, limiter
from app.flash import flash
from app.models import User
from app.services.csrf import verify_csrf
from app.services.security import verify_password
from app.templating import render

router = APIRouter()


def _rate_limited(limit_string: str):
    """
    Applies slowapi's rate limit, except during tests. slowapi's Limiter
    keeps its counters in memory for the whole process, not reset between
    tests -- with dozens of tests now logging in via the `logged_in_client`
    fixture, the real "5 per minute" limit gets exhausted partway through a
    single test run, turning later logins into 429s instead of testing what
    they're meant to. Rather than lean on an internal reset API, this just
    skips applying the decorator at all when ENVIRONMENT=testing (set by
    tests/conftest.py) -- unambiguous, no reliance on slowapi internals.
    """
    if settings.ENVIRONMENT == "testing":
        return lambda func: func
    return limiter.limit(limit_string)


@router.get("/login")
def login_form(request: Request, next: str = "/dashboard"):
    """App Flow Screen 1. Already-logged-in users skip straight to the dashboard."""
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "login.html", {"next": next})


@router.post("/login")
@_rate_limited("5/minute")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next: str = Form("/dashboard"),
    db: Session = Depends(get_db),
):
    verify_csrf(request, csrf_token)

    user = db.query(User).filter(User.username == username).first()

    # Deliberately the same error whether the username doesn't exist, the
    # password is wrong, or the account is inactive — App Flow Screen 1:
    # never reveal which one it was. Password field is cleared; username is
    # retained (re-rendered below, `password` is simply never passed back).
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        flash(request, "Invalid username or password.", "error")
        return render(request, "login.html", {"next": next, "username": username}, status_code=401)

    now = datetime.now(timezone.utc)
    request.session["user_id"] = user.id
    request.session["login_time"] = now.isoformat()
    request.session["last_activity"] = now.isoformat()

    user.last_login_at = now
    db.commit()

    return RedirectResponse(url=next or "/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    verify_csrf(request, csrf_token)
    request.session.clear()
    flash(request, "You have been logged out.", "info")
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
