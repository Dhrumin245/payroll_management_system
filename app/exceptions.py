class NotAuthenticatedException(Exception):
    """
    Raised by app.dependencies.get_current_user when there's no valid
    session. Caught by the exception handler registered in app/main.py,
    which redirects to /login — this is FastAPI's equivalent of Flask-Login's
    automatic redirect-on-@login_required behavior.
    """
