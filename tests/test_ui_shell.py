"""
Phase 3 checks: the base shell renders correctly and a 404 falls back to the
styled error page. Run with: pytest
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_route_renders_styled_404():
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert "Page not found" in response.text


def test_login_page_uses_display_heading_and_no_navbar():
    response = client.get("/login")
    assert response.status_code == 200
    assert "app-navbar" not in response.text  # public page, no authenticated shell
    assert "display-heading" in response.text
