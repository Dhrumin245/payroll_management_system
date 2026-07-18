"""
Phase 10: Leave Management System (LMS) tests.
"""
from datetime import date, datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.dependencies import SessionLocal, engine
from app.main import app
from app.models import Base, Employee, LeaveRequest, LeaveType, LeaveBalance, AttendanceRecord, User
from app.services.security import hash_password
from app.services.leave_service import (
    create_leave_request,
    approve_leave_request,
    reject_leave_request,
    get_employee_leave_balances,
    sync_attendance_from_leaves,
)
from tests.conftest import extract_csrf_token

# ---------------------------------------------------------------------------
# Setup and Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


_emp_counter = 0


def _seed_employee_and_user(username: str, role: str, code: str = None) -> tuple[int, int]:
    """Seeds employee and user; returns (employee_id, user_id)."""
    global _emp_counter
    if code is None:
        _emp_counter += 1
        code = f"EMP{5000 + _emp_counter:04d}"

    db = SessionLocal()
    try:
        emp = Employee(
            employee_code=code,
            full_name="LMS Tester",
            designation="Developer",
            joining_date=date(2024, 1, 1),
            status="active",
        )
        db.add(emp)
        db.flush()

        user = User(
            username=username,
            password_hash=hash_password("Pass123!"),
            role=role,
            employee_id=emp.id,
        )
        db.add(user)
        db.commit()
        return emp.id, user.id
    finally:
        db.close()


def _login(client, username, role: str = "admin") -> str:
    """Log in and return a CSRF token scraped from the post-login landing page."""
    login_page = client.get("/login")
    csrf = extract_csrf_token(login_page.text)
    client.post(
        "/login",
        data={"username": username, "password": "Pass123!", "csrf_token": csrf},
        follow_redirects=True,
    )
    # Employee-role users land on /portal; everyone else lands on /dashboard
    landing = "/portal" if role == "employee" else "/dashboard"
    page = client.get(landing)
    return extract_csrf_token(page.text)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestLeaveManagementSystem:
    def test_create_and_query_leave_type(self, client):
        # Log in admin to call config
        _seed_employee_and_user("lms_admin", "admin")
        csrf = _login(client, "lms_admin")

        # Create leave type
        resp = client.post(
            "/leaves/types/new",
            data={"name": "Sick Leave", "max_days": "10", "is_paid": "1", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Sick Leave" in resp.text

        db = SessionLocal()
        lt = db.query(LeaveType).filter(LeaveType.name == "Sick Leave").first()
        assert lt is not None
        assert lt.max_days_per_year == Decimal("10.0")
        assert lt.is_paid is True
        db.close()

    def test_employee_can_submit_leave_request(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp", "employee")
        
        # Seed leave type
        db = SessionLocal()
        lt = LeaveType(name="Annual Leave", max_days_per_year=15, is_paid=True)
        db.add(lt)
        db.commit()
        lt_id = lt.id
        db.close()

        csrf = _login(client, "lms_emp", role="employee")

        # Submit leave request
        resp = client.post(
            "/portal/leaves/new",
            data={
                "leave_type_id": str(lt_id),
                "start_date": "2025-06-02",
                "end_date": "2025-06-06",
                "reason": "Family holiday",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "submitted successfully" in resp.text

        # Verify DB request state
        db = SessionLocal()
        req = db.query(LeaveRequest).filter(LeaveRequest.employee_id == emp_id).first()
        assert req is not None
        assert req.status == "pending"
        assert req.start_date == date(2025, 6, 2)
        assert req.end_date == date(2025, 6, 6)
        db.close()

    def test_overlapping_leave_request_raises_error(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp2", "employee")
        db = SessionLocal()
        lt = LeaveType(name="Casual Leave", max_days_per_year=12, is_paid=True)
        db.add(lt)
        db.commit()
        lt_id = lt.id
        db.close()

        # Submit first request successfully
        db = SessionLocal()
        create_leave_request(db, emp_id, lt_id, date(2025, 6, 2), date(2025, 6, 5), "Trip")
        db.close()

        csrf = _login(client, "lms_emp2", role="employee")

        # Attempt to submit overlapping request
        resp = client.post(
            "/portal/leaves/new",
            data={
                "leave_type_id": str(lt_id),
                "start_date": "2025-06-04",
                "end_date": "2025-06-07",
                "reason": "Overlapping Trip",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "overlapping leave request" in resp.text

    def test_manager_can_approve_leave_request(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp3", "employee")
        _, mgr_id = _seed_employee_and_user("lms_mgr", "manager")

        db = SessionLocal()
        lt = LeaveType(name="Sick Leave", max_days_per_year=10, is_paid=True)
        db.add(lt)
        db.commit()
        lt_id = lt.id
        # Create pending request
        req = create_leave_request(db, emp_id, lt_id, date(2025, 6, 2), date(2025, 6, 4))
        req_id = req.id
        db.close()

        csrf = _login(client, "lms_mgr")

        # Approve request
        resp = client.post(
            f"/leaves/{req_id}/approve",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "approved and synced" in resp.text

        db = SessionLocal()
        req_db = db.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
        assert req_db.status == "approved"
        assert req_db.approved_by_user_id == mgr_id
        
        # Verify leave balance incremented
        bal = db.query(LeaveBalance).filter(LeaveBalance.employee_id == emp_id, LeaveBalance.year == 2025).first()
        assert bal is not None
        assert bal.days_used == Decimal("3.0")  # June 2 (Mon), 3 (Tue), 4 (Wed)
        db.close()

    def test_sunday_is_excluded_from_approved_leave_count(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp4", "employee")
        _, mgr_id = _seed_employee_and_user("lms_mgr2", "manager")

        db = SessionLocal()
        lt = LeaveType(name="Weekly Off Test", max_days_per_year=10, is_paid=True)
        db.add(lt)
        db.commit()
        
        # Request spans a weekend: Friday (June 6) to Monday (June 9). Sunday is June 8.
        req = create_leave_request(db, emp_id, lt.id, date(2025, 6, 6), date(2025, 6, 9))
        req_id = req.id
        db.close()

        csrf = _login(client, "lms_mgr2")
        client.post(f"/leaves/{req_id}/approve", data={"csrf_token": csrf})

        db = SessionLocal()
        bal = db.query(LeaveBalance).filter(LeaveBalance.employee_id == emp_id, LeaveBalance.year == 2025).first()
        # Calendar days: 6, 7, 8, 9 (4 days). June 8 is Sunday -> should be exactly 3 days used.
        assert bal.days_used == Decimal("3.0")
        db.close()

    def test_exceeding_annual_allowance_fails_approval(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp5", "employee")
        _, mgr_id = _seed_employee_and_user("lms_mgr3", "manager")

        db = SessionLocal()
        lt = LeaveType(name="Restricted Leave", max_days_per_year=2, is_paid=True)
        db.add(lt)
        db.commit()
        
        # Request for 3 working days (June 2 to June 4) exceeds limit of 2 days
        req = create_leave_request(db, emp_id, lt.id, date(2025, 6, 2), date(2025, 6, 4))
        req_id = req.id
        db.close()

        csrf = _login(client, "lms_mgr3")
        resp = client.post(f"/leaves/{req_id}/approve", data={"csrf_token": csrf}, follow_redirects=True)
        assert resp.status_code == 200
        assert "Leave limit exceeded" in resp.text

        db = SessionLocal()
        req_db = db.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
        assert req_db.status == "pending"  # Approval rolled back
        db.close()

    def test_attendance_sync_updates_attendance_grid(self, client):
        emp_id, _ = _seed_employee_and_user("lms_emp6", "employee")
        _, mgr_id = _seed_employee_and_user("lms_mgr4", "manager")

        db = SessionLocal()
        lt = LeaveType(name="Sync Test", max_days_per_year=10, is_paid=True)
        db.add(lt)
        db.commit()
        req = create_leave_request(db, emp_id, lt.id, date(2025, 6, 2), date(2025, 6, 4))
        req_id = req.id
        db.close()

        csrf = _login(client, "lms_mgr4")
        
        # Prior to approval, grid should have 0 days on leave
        resp = client.get("/attendance/2025-06")
        assert 'value="3.0"' not in resp.text

        # Approve leave
        client.post(f"/leaves/{req_id}/approve", data={"csrf_token": csrf})

        # Reload attendance page -> should trigger auto-sync
        resp = client.get("/attendance/2025-06")
        assert resp.status_code == 200
        # Days on leave should be populated with 3
        assert 'name="days_on_leave" value="3"' in resp.text or 'name="days_on_leave" value="3.0"' in resp.text
        # Days present should default to total working days (25) minus leave days (3) = 22
        assert 'name="days_present" value="22"' in resp.text or 'name="days_present" value="22.0"' in resp.text
