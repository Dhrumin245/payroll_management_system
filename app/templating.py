from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.flash import get_flashed_messages
from app.services.csrf import get_csrf_token

templates = Jinja2Templates(directory="app/templates")


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200) -> HTMLResponse:
    """
    Thin wrapper around Jinja2Templates.TemplateResponse that automatically
    injects `request` (required by Jinja2Templates), any flashed messages,
    and the current CSRF token — so individual routes/templates don't have
    to remember to wire these up every time.

    IMPORTANT: Starlette's TemplateResponse() takes `request` as its first
    positional argument (this changed at some point to support Jinja2
    context processors properly; older code/tutorials often show the
    previous `TemplateResponse(name, context)` calling convention). Getting
    this order wrong doesn't raise a clear error -- it silently shifts every
    argument over by one slot, and Jinja2 ends up trying to use the context
    dict as a template-cache key, which fails with a confusing
    "unhashable type: 'dict'" deep inside Jinja2's internals, far from the
    actual mistake. If you ever see that error, check this exact line first.
    """
    full_context: dict = {
        "request": request,
        "flashes": get_flashed_messages(request),
        "csrf_token": get_csrf_token(request),
    }
    if context:
        full_context.update(context)
    return templates.TemplateResponse(request, name, full_context, status_code=status_code)
