"""
Shared FastAPI dependencies — the things injected into routes via Depends().
"""
from datetime import datetime, timedelta, timezone
from typing import Generator

from fastapi import Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.exceptions import NotAuthenticatedException, NotAuthorizedException
from app.models import User

# --- Database session -------------------------------------------------------
# SQLite needs check_same_thread=False since FastAPI can use multiple threads
# per process; this has no effect once DATABASE_URL points at Postgres.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """
        SQLite does NOT enforce foreign key constraints by default, even
        though the schema declares them — without this, ON DELETE
        RESTRICT/CASCADE (Backend Schema §7) would silently do nothing.
        Has no effect once DATABASE_URL points at Postgres, which enforces
        FKs natively regardless.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """Yields one SQLAlchemy session per request, closing it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Rate limiting -----------------------------------------------------------
# Wired into the app in main.py; actually applied to POST /login in
# app/routers/auth.py.
limiter = Limiter(key_func=get_remote_address)


# --- Auth ---------------------------------------------------------------------
# Backend Schema §6: 30-minute idle timeout, 8-hour absolute maximum. Both are
# tracked via timestamps stored in the session payload itself, since
# Starlette's SessionMiddleware doesn't distinguish idle vs. absolute the way
# a dedicated config key would.
IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=8)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    FastAPI's equivalent of Flask-Login's @login_required: raises
    NotAuthenticatedException (handled in main.py by redirecting to /login)
    whenever there's no valid, unexpired session.
    """
    user_id = request.session.get("user_id")
    login_time_str = request.session.get("login_time")
    last_activity_str = request.session.get("last_activity")

    if not user_id or not login_time_str or not last_activity_str:
        raise NotAuthenticatedException()

    now = datetime.now(timezone.utc)
    login_time = datetime.fromisoformat(login_time_str)
    last_activity = datetime.fromisoformat(last_activity_str)

    if (now - last_activity) > IDLE_TIMEOUT or (now - login_time) > ABSOLUTE_TIMEOUT:
        request.session.clear()
        raise NotAuthenticatedException()

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        request.session.clear()
        raise NotAuthenticatedException()

    request.session["last_activity"] = now.isoformat()
    return user


# --- Role guards -------------------------------------------------------------
# These are FastAPI dependency factories that build on get_current_user and
# raise NotAuthorizedException when the authenticated user lacks the required
# role tier.  The exception is caught by the handler in main.py and rendered
# as a 403 page — never a bare JSON response, since this is an HTMX/Jinja app.

def require_admin(user: User = Depends(get_current_user)) -> User:
    """Only 'admin' role users may proceed.  Returns the user on success."""
    if user.role != "admin":
        raise NotAuthorizedException()
    return user


def require_manager_or_above(user: User = Depends(get_current_user)) -> User:
    """Both 'admin' and 'manager' role users may proceed; 'employee' is denied."""
    if user.role == "employee":
        raise NotAuthorizedException()
    return user
