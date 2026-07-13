"""
Phase 4b checks: attendance entry, working-day validation, and period
locking once a payroll run exists. Run with: pytest
"""
from datetime import date

from app.dependencies import SessionLocal
from app.models import AttendanceRecord, Employee, PayrollRun, User

_EMPLOYEE_PAYLOAD = {
    "full_name": "Test Employee",
    "employee_code": "EMP0001",
    "designation": "Engineer",
    "joining_date": "2026-01-01",
    "basic_pay": "50000",
}


def _create_employee(client, csrf_token) -> int:
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))
    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()
    return employee_id


def test_attendance_redirects_to_current_period(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/attendance", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/attendance/")


def test_attendance_shows_empty_state_with_no_active_employees(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/attendance/2026-07")
    assert response.status_code == 200
    assert "No active employees" in response.text


def test_save_attendance_success(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)

    response = client.post(
        "/attendance/2026-07",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["22"],
            "days_on_leave": ["0"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Attendance saved for July 2026" in response.text

    db = SessionLocal()
    record = db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id).first()
    assert record is not None
    assert record.days_present == 22
    assert record.total_working_days > 0
    db.close()


def test_revisiting_saved_period_shows_saved_badge_and_values(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)
    client.post(
        "/attendance/2026-07",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["22"],
            "days_on_leave": ["0"],
        },
    )

    response = client.get("/attendance/2026-07")
    assert "Saved" in response.text
    assert 'value="22"' in response.text


def test_attendance_exceeding_working_days_is_rejected(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)

    # 30 + 5 = 35 exceeds any possible working-day count for a single month.
    response = client.post(
        "/attendance/2026-07",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["30"],
            "days_on_leave": ["5"],
        },
    )
    assert response.status_code == 400
    assert "cannot exceed" in response.text

    db = SessionLocal()
    assert db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id).first() is None
    db.close()


def test_locked_period_blocks_attendance_save(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)

    db = SessionLocal()
    admin = db.query(User).filter(User.username == "testadmin").first()
    db.add(
        PayrollRun(
            period=date(2026, 7, 1),
            status="completed",
            total_gross=50000,
            total_deductions=5000,
            total_net_pay=45000,
            employee_count=1,
            run_by_user_id=admin.id,
        )
    )
    db.commit()
    db.close()

    response = client.get("/attendance/2026-07")
    assert "locked" in response.text.lower()

    response = client.post(
        "/attendance/2026-07",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["22"],
            "days_on_leave": ["0"],
        },
        follow_redirects=True,
    )
    assert "already been run" in response.text

    db = SessionLocal()
    assert db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == employee_id).first() is None
    db.close()
