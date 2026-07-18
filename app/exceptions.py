class NotAuthenticatedException(Exception):
    """
    Raised by app.dependencies.get_current_user when there's no valid
    session. Caught by the exception handler registered in app/main.py,
    which redirects to /login — this is FastAPI's equivalent of Flask-Login's
    automatic redirect-on-@login_required behavior.
    """


class NotAuthorizedException(Exception):
    """
    Raised by role-guard dependencies (require_admin, require_manager_or_above)
    when a logged-in user lacks the required role for the requested resource.
    Caught by the exception handler in app/main.py, which renders the 403 page.
    """
