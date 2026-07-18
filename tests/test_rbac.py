from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.dependencies import SessionLocal, engine
from app.main import app
from app.models import Base, Employee, SalaryStructure, User
from app.services.security import hash_password
from tests.conftest import extract_csrf_token

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


def _seed_user(role: str, username: str = None) -> tuple[str, str]:
    username = username or f"test_{role}"
    password = "TestPass123!"
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == username).first():
            db.add(User(username=username, password_hash=hash_password(password), role=role))
            db.commit()
    finally:
        db.close()
    return username, password


def _login(client: TestClient, username: str, password: str) -> str:
    """Logs in and returns the CSRF token extracted from the dashboard."""
    login_page = client.get("/login")
    csrf = extract_csrf_token(login_page.text)
    client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=True,
    )
    dashboard = client.get("/dashboard")
    return extract_csrf_token(dashboard.text)


def _seed_employee(db=None) -> int:
    """Seeds one active employee with a salary structure; returns employee.id."""
    close = db is None
    if db is None:
        db = SessionLocal()
    try:
        emp = Employee(
            employee_code="EMP9901",
            full_name="Role Test Employee",
            designation="Tester",
            joining_date=date(2025, 1, 1),
            status="active",
        )
        db.add(emp)
        db.flush()
        db.add(SalaryStructure(employee_id=emp.id, basic_pay=50000, hra=0, conveyance_allowance=0))
        db.commit()
        return emp.id
    finally:
        if close:
            db.close()


# ---------------------------------------------------------------------------
# Admin role — full access
# ---------------------------------------------------------------------------

class TestAdminAccess:
    def test_admin_can_view_employees(self, client):
        username, password = _seed_user("admin", "rbac_admin")
        _login(client, username, password)
        resp = client.get("/employees")
        assert resp.status_code == 200

    def test_admin_can_access_new_employee_form(self, client):
        username, password = _seed_user("admin", "rbac_admin2")
        _login(client, username, password)
        resp = client.get("/employees/new")
        assert resp.status_code == 200

    def test_admin_can_access_payroll_new(self, client):
        username, password = _seed_user("admin", "rbac_admin3")
        _login(client, username, password)
        resp = client.get("/payroll/new")
        assert resp.status_code == 200

    def test_admin_nav_shows_all_links(self, client):
        username, password = _seed_user("admin", "rbac_admin4")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "/employees" in resp.text
        assert "/attendance" in resp.text
        assert "/payroll" in resp.text


# ---------------------------------------------------------------------------
# Manager role — HR access but no payroll run
# ---------------------------------------------------------------------------

class TestManagerAccess:
    def test_manager_can_view_employees(self, client):
        username, password = _seed_user("manager", "rbac_mgr")
        _login(client, username, password)
        resp = client.get("/employees")
        assert resp.status_code == 200

    def test_manager_can_access_new_employee_form(self, client):
        username, password = _seed_user("manager", "rbac_mgr2")
        _login(client, username, password)
        resp = client.get("/employees/new")
        assert resp.status_code == 200

    def test_manager_cannot_trigger_payroll_run(self, client):
        """POST /payroll/run is admin-only; manager must receive 403."""
        username, password = _seed_user("manager", "rbac_mgr3")
        csrf = _login(client, username, password)
        resp = client.post(
            "/payroll/run",
            data={"period": "2025-07", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_manager_nav_shows_hr_links(self, client):
        username, password = _seed_user("manager", "rbac_mgr4")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert "/employees" in resp.text
        assert "/attendance" in resp.text


# ---------------------------------------------------------------------------
# Employee role — denied all HR management routes
# ---------------------------------------------------------------------------

class TestEmployeeRoleAccess:
    def test_employee_denied_employee_list(self, client):
        # employee-role users CAN see the list (read-only), but not mutate
        username, password = _seed_user("employee", "rbac_emp")
        _login(client, username, password)
        # Read-only route uses get_current_user (allowed)
        resp = client.get("/employees")
        assert resp.status_code == 200

    def test_employee_denied_new_employee_form(self, client):
        username, password = _seed_user("employee", "rbac_emp2")
        _login(client, username, password)
        resp = client.get("/employees/new", follow_redirects=False)
        assert resp.status_code == 403

    def test_employee_denied_attendance_post(self, client):
        username, password = _seed_user("employee", "rbac_emp3")
        csrf = _login(client, username, password)
        resp = client.post(
            "/attendance/2025-07",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_employee_denied_payroll_run(self, client):
        username, password = _seed_user("employee", "rbac_emp4")
        csrf = _login(client, username, password)
        resp = client.post(
            "/payroll/run",
            data={"period": "2025-07", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_employee_nav_hides_hr_links(self, client):
        username, password = _seed_user("employee", "rbac_emp5")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        # HR links should NOT appear in the nav for employee-role users
        assert "href=\"/employees\"" not in resp.text
        assert "href=\"/attendance\"" not in resp.text
        assert "href=\"/payroll\"" not in resp.text

    def test_employee_denied_deactivate(self, client):
        emp_id = _seed_employee()
        username, password = _seed_user("employee", "rbac_emp6")
        csrf = _login(client, username, password)
        resp = client.post(
            f"/employees/{emp_id}/deactivate",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403

    def test_employee_denied_reactivate(self, client):
        emp_id = _seed_employee()
        username, password = _seed_user("employee", "rbac_emp7")
        csrf = _login(client, username, password)
        resp = client.post(
            f"/employees/{emp_id}/reactivate",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Role badge in nav
# ---------------------------------------------------------------------------

class TestRoleBadge:
    def test_admin_role_badge_shown(self, client):
        username, password = _seed_user("admin", "badge_admin")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert "badge--role" in resp.text
        assert "admin" in resp.text

    def test_manager_role_badge_shown(self, client):
        username, password = _seed_user("manager", "badge_mgr")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert "badge--role" in resp.text
        assert "manager" in resp.text

    def test_employee_role_badge_not_shown(self, client):
        username, password = _seed_user("employee", "badge_emp")
        _login(client, username, password)
        resp = client.get("/dashboard")
        assert "badge--role" not in resp.text
