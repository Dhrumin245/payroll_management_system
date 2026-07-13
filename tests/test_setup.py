"""
Phase 0 exit-criteria check, updated for Phase 1: the app boots and serves
requests. `/` now redirects through to /dashboard -> /login (since there's
no session yet) rather than rendering a standalone placeholder.
Run with: pytest
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_redirects_through_to_login_when_unauthenticated():
    response = client.get("/")  # TestClient follows the redirect chain by default
    assert response.status_code == 200
    assert "Payroll Management System" in response.text
