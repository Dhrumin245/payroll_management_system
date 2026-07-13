"""
CSRF protection via a synchronizer token tied to the session.

The TRD/Backend Schema named `starlette-csrf` as one option "or a custom
session-tied token" as the explicitly allowed alternative — this is that
alternative. It's implemented by hand rather than via the third-party package
because starlette-csrf is built around a header-based double-submit-cookie
pattern (suited to AJAX/API clients setting a custom header), which doesn't
map cleanly onto plain HTML <form> POSTs with no JavaScript — exactly this
app's architecture (TRD §4: server-rendered Jinja2, no SPA). A synchronizer
token stored in the session and rendered as a hidden form field is the
standard pattern for that shape of app, and doesn't depend on guessing at a
third-party package's exact request-parsing behavior.
"""
import secrets

from fastapi import HTTPException, Request, status


def get_csrf_token(request: Request) -> str:
    """Returns this session's CSRF token, generating one on first use."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, submitted_token: str) -> None:
    """Raises 403 if the submitted token doesn't match the session's token."""
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not secrets.compare_digest(submitted_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing CSRF token.")
