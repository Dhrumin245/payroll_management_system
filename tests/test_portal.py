"""
Phase 9: Employee Self-Service (ESS) Portal tests.
"""
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.dependencies import SessionLocal, engine
from app.main import app
from app.models import Base, Employee, EmployeeBankDetails, PayrollLineItem, PayrollRun, SalaryStructure, User
from app.services.security import hash_password
from tests.conftest import extract_csrf_token

# ---------------------------------------------------------------------------
# Setup and Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


def _seed_employee_with_user(username: str, code: str) -> tuple[int, str, str]:
    """Helper to seed an employee, set up user account, and return (emp_id, username, password)."""
    password = "CorrectPass123!"
    db = SessionLocal()
    try:
        # Seed employee
        emp = Employee(
            employee_code=code,
            full_name=f"Self Service {username}",
            designation="Developer",
            joining_date=date(2024, 1, 1),
            status="active",
        )
        db.add(emp)
        db.flush()

        # Seed bank details
        bank = EmployeeBankDetails(
            employee_id=emp.id,
            account_holder_name=emp.full_name,
            ifsc_code="IFSC0001",
            bank_name="Test Bank",
        )
        bank.account_number = "123456789012"  # Encrypted automatically
        db.add(bank)

        # Seed salary structure
        salary = SalaryStructure(
            employee_id=emp.id,
            basic_pay=75000,
            hra=30000,
            conveyance_allowance=2000,
        )
        db.add(salary)
        db.flush()

        # Create user linked to employee
        user = User(
            username=username,
            password_hash=hash_password(password),
            role="employee",
            employee_id=emp.id,
        )
        db.add(user)
        db.commit()
        return emp.id, username, password
    finally:
        db.close()


def _seed_payroll_run(db, employee_id: int) -> int:
    """Seeds one completed payroll run and returns its id."""
    admin = User(username="tempadmin", password_hash=hash_password("adminpass"), role="admin")
    db.add(admin)
    db.flush()

    run = PayrollRun(
        period=date(2025, 6, 1),
        status="completed",
        total_gross=75000,
        total_deductions=5000,
        total_net_pay=70000,
        employee_count=1,
        run_by_user_id=admin.id,
    )
    db.add(run)
    db.flush()

    item = PayrollLineItem(
        payroll_run_id=run.id,
        employee_id=employee_id,
        employee_code_snapshot="EMP001",
        employee_name_snapshot="Employee One",
        days_present_snapshot=22,
        days_on_leave_snapshot=0,
        gross_pay=75000,
        total_deductions=5000,
        net_pay=70000,
    )
    db.add(item)
    db.commit()
    return run.id


def _login(client, username, password) -> str:
    login_page = client.get("/login")
    csrf = extract_csrf_token(login_page.text)
    response = client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    # Check redirect status
    assert response.status_code == 303
    return response.headers["location"]


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestEmployeePortalFlows:
    def test_employee_login_redirects_to_portal_dashboard(self, client):
        _, username, password = _seed_employee_with_user("ess_emp1", "EMP001")
        redirect_url = _login(client, username, password)
        assert redirect_url == "/portal"

    def test_employee_portal_dashboard_loads(self, client):
        emp_id, username, password = _seed_employee_with_user("ess_emp2", "EMP002")
        db = SessionLocal()
        _seed_payroll_run(db, emp_id)
        db.close()

        _login(client, username, password)
        resp = client.get("/portal")
        assert resp.status_code == 200
        assert "Welcome" in resp.text
        assert "Developer" in resp.text
        assert "₹70,000.00" in resp.text  # latest net pay displayed

    def test_employee_can_view_own_payslips(self, client):
        emp_id, username, password = _seed_employee_with_user("ess_emp3", "EMP003")
        db = SessionLocal()
        _seed_payroll_run(db, emp_id)
        db.close()

        _login(client, username, password)
        resp = client.get("/portal/payslips")
        assert resp.status_code == 200
        assert "June 2025" in resp.text
        assert "₹70,000.00" in resp.text

    def test_employee_can_download_own_payslip_pdf(self, client):
        emp_id, username, password = _seed_employee_with_user("ess_emp4", "EMP004")
        db = SessionLocal()
        run_id = _seed_payroll_run(db, emp_id)
        db.close()

        _login(client, username, password)
        resp = client.get(f"/portal/payslips/{run_id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "filename=" in resp.headers["content-disposition"]

    def test_employee_cannot_download_others_payslip_pdf(self, client):
        emp_id1, username1, password1 = _seed_employee_with_user("ess_emp5", "EMP005")
        emp_id2, username2, password2 = _seed_employee_with_user("ess_emp6", "EMP006")
        db = SessionLocal()
        run_id_other = _seed_payroll_run(db, emp_id2)
        db.close()

        # Log in as user 1, try to download user 2's payslip
        _login(client, username1, password1)
        resp = client.get(f"/portal/payslips/{run_id_other}")
        assert resp.status_code == 403
        assert "Access denied" in resp.text

    def test_employee_can_view_own_attendance_history(self, client):
        _, username, password = _seed_employee_with_user("ess_emp7", "EMP007")
        _login(client, username, password)
        resp = client.get("/portal/attendance")
        assert resp.status_code == 200
        assert "My Attendance" in resp.text

    def test_employee_can_view_own_profile(self, client):
        _, username, password = _seed_employee_with_user("ess_emp8", "EMP008")
        _login(client, username, password)
        resp = client.get("/portal/profile")
        assert resp.status_code == 200
        assert "My Profile" in resp.text
        assert "********9012" in resp.text  # masked bank account number matches suffix

    def test_admin_redirected_away_from_portal_dashboard(self, client):
        db = SessionLocal()
        admin = User(username="adminuser", password_hash=hash_password("adminpass"), role="admin")
        db.add(admin)
        db.commit()
        db.close()

        # Log in admin
        login_page = client.get("/login")
        csrf = extract_csrf_token(login_page.text)
        client.post("/login", data={"username": "adminuser", "password": "adminpass", "csrf_token": csrf})

        # Hit /portal -> redirect to /dashboard
        resp = client.get("/portal", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/dashboard"
