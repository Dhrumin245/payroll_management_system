"""
Points the entire test suite at a dedicated test database instead of the
real one — this must run before ANY app module is imported anywhere, since
app.config reads DATABASE_URL from the environment at import time and
app.dependencies builds its `engine` from that immediately after.

pytest guarantees conftest.py in a directory is loaded before that
directory's test files are collected/imported, which is what makes setting
the env var here (rather than in a fixture) actually work.

Without this, per-test `Base.metadata.create_all()` / `drop_all()` calls run
against whatever DATABASE_URL points at — which, before this file existed,
was the real dev.db. That's exactly what happened once: pytest was silently
dropping every table in the real database on each run.
"""
import os

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ENVIRONMENT"] = "testing"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("BANK_ENCRYPTION_KEY", Fernet.generate_key().decode())

# Guarantee a completely clean slate every session. Base.metadata.create_all()
# only creates tables that don't already exist, so a test.db left over from
# an interrupted/crashed earlier run (Ctrl+C mid-test, a hung process) can
# leave stale tables or rows sitting in the file -- since the file itself
# persists across separate `pytest` invocations, not just across tests
# within one run. That's a real, if intermittent, source of flaky failures
# (a test seeing data it didn't create). Deleting it here, before the engine
# ever connects, removes that possibility entirely.
if os.path.exists("test.db"):
    os.remove("test.db")

import re

import pytest
from fastapi.testclient import TestClient

from app.dependencies import SessionLocal, engine
from app.main import app
from app.models import Base, User
from app.services.security import hash_password


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "CSRF token not found in rendered page"
    return match.group(1)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def logged_in_client(client):
    """A TestClient with an authenticated admin session, plus that session's CSRF token."""
    db = SessionLocal()
    db.add(User(username="testadmin", password_hash=hash_password("testpass123"), role="admin"))
    db.commit()
    db.close()

    login_page = client.get("/login")
    csrf_token = extract_csrf_token(login_page.text)
    client.post("/login", data={"username": "testadmin", "password": "testpass123", "csrf_token": csrf_token})
    return client, csrf_token
