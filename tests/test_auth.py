"""
Phase 1 checks: the login wall. Run with: pytest

Runs against a dedicated test.db (see tests/conftest.py), never the real
dev database.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.dependencies import SessionLocal, engine
from app.main import app
from app.models import Base, User
from app.services.security import hash_password


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "CSRF token not found in rendered page"
    return match.group(1)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_admin(client):
    db = SessionLocal()
    user = User(username="testadmin", password_hash=hash_password("correct-horse-battery"), role="admin")
    db.add(user)
    db.commit()
    db.close()
    return "testadmin", "correct-horse-battery"


def test_dashboard_redirects_to_login_when_unauthenticated(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_login_with_wrong_password_shows_generic_error(client, seeded_admin):
    username, _ = seeded_admin
    login_page = client.get("/login")
    csrf_token = _extract_csrf_token(login_page.text)

    response = client.post(
        "/login",
        data={"username": username, "password": "wrong-password", "csrf_token": csrf_token},
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.text
    # Password field must never be echoed back, per App Flow Screen 1
    assert "wrong-password" not in response.text


def test_login_with_correct_credentials_reaches_dashboard(client, seeded_admin):
    username, password = seeded_admin
    login_page = client.get("/login")
    csrf_token = _extract_csrf_token(login_page.text)

    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Welcome" in response.text


def test_login_rejects_bad_csrf_token(client, seeded_admin):
    username, password = seeded_admin
    client.get("/login")  # establishes a session with a real csrf_token

    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": "not-the-real-token"},
    )
    assert response.status_code == 403


def test_logout_clears_session(client, seeded_admin):
    username, password = seeded_admin
    login_page = client.get("/login")
    csrf_token = _extract_csrf_token(login_page.text)
    client.post("/login", data={"username": username, "password": password, "csrf_token": csrf_token})

    dashboard = client.get("/dashboard")
    logout_csrf = _extract_csrf_token(dashboard.text)
    client.post("/logout", data={"csrf_token": logout_csrf})

    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
