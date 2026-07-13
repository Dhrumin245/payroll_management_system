from fastapi import Request


def flash(request: Request, message: str, category: str = "info") -> None:
    """
    Stashes a flash message in the session. FastAPI/Starlette has no built-in
    flash() the way Flask does, so this — plus get_flashed_messages() below —
    reproduces the same read-once pattern by hand (Implementation Plan, Phase 1).
    """
    flashes = request.session.get("_flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["_flashes"] = flashes


def get_flashed_messages(request: Request) -> list[dict]:
    """Returns and clears any flashed messages for this session — read-once."""
    return request.session.pop("_flashes", [])
