"""
Phase 6 checks: the Dashboard now reflects real data (Phase 3 shipped it
with hardcoded placeholders and no later phase explicitly came back to
wire it up -- this closes that gap). Run with: pytest
"""
from app.dependencies import SessionLocal
from app.models import Employee, PayrollRun

_EMPLOYEE_PAYLOAD = {
    "full_name": "Test Employee",
    "employee_code": "EMP0001",
    "designation": "Engineer",
    "joining_date": "2026-01-01",
    "basic_pay": "50000",
}


def test_dashboard_shows_true_empty_state_with_no_data(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "No employees yet" in response.text
    assert "No payroll runs yet" in response.text


def test_dashboard_shows_real_active_employee_count(logged_in_client):
    client, csrf_token = logged_in_client
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))

    response = client.get("/dashboard")
    assert "No employees yet" not in response.text
    # The active employee count renders inside a font-mono value cell;
    # confirm it's "1", not the old hardcoded placeholder value.
    assert ">1<" in response.text


def test_dashboard_shows_recent_run_after_payroll_is_run(logged_in_client):
    client, csrf_token = logged_in_client
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))

    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()

    client.post(
        "/attendance/2026-07",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["27"],
            "days_on_leave": ["0"],
        },
    )
    client.post("/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"})

    response = client.get("/dashboard")
    assert "No payroll runs yet" not in response.text
    assert "July 2026" in response.text

    db = SessionLocal()
    run_id = db.query(PayrollRun).first().id
    db.close()
    assert f'/payroll/{run_id}"' in response.text  # recent-run row links to the actual run
