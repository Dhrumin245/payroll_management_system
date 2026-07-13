"""
Phase 4c checks: the full "Run Payroll" HTTP flow -- readiness guards,
successful runs, duplicate-run blocking, and the all-or-nothing rollback
guarantee. Run with: pytest

(The payroll math itself is covered exhaustively, dependency-free, in
test_payroll_engine.py -- these tests exercise the persistence and routing
layer built on top of it.)
"""
from datetime import date

from app.dependencies import SessionLocal
from app.models import Employee, PayrollLineItem, PayrollRun

_EMPLOYEE_PAYLOAD = {
    "full_name": "Test Employee",
    "employee_code": "EMP0001",
    "designation": "Engineer",
    "joining_date": "2026-01-01",
    "basic_pay": "50000",
    "component_type": ["deduction"],
    "component_name": ["Professional Tax"],
    "component_amount": ["200"],
}


def _create_employee(client, csrf_token) -> int:
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))
    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()
    return employee_id


def _submit_attendance(client, csrf_token, employee_id, period, days_present="27", days_on_leave="0"):
    client.post(
        f"/attendance/{period}",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": [days_present],
            "days_on_leave": [days_on_leave],
        },
    )


def test_new_payroll_run_shows_incomplete_attendance(logged_in_client):
    client, csrf_token = logged_in_client
    _create_employee(client, csrf_token)

    response = client.get("/payroll/new?period=2026-07")
    assert response.status_code == 200
    assert "incomplete" in response.text.lower()
    assert "disabled" in response.text


def test_running_payroll_with_incomplete_attendance_is_blocked(logged_in_client):
    client, csrf_token = logged_in_client
    _create_employee(client, csrf_token)

    response = client.post(
        "/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"}, follow_redirects=True
    )
    assert "Attendance is incomplete" in response.text

    db = SessionLocal()
    assert db.query(PayrollRun).count() == 0
    db.close()


def test_full_payroll_run_succeeds_and_produces_correct_totals(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)
    _submit_attendance(client, csrf_token, employee_id, "2026-07")

    response = client.post(
        "/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Payroll Summary" in response.text
    assert "Test Employee" in response.text

    db = SessionLocal()
    run = db.query(PayrollRun).filter_by(period=date(2026, 7, 1)).first()
    assert run is not None
    assert run.employee_count == 1
    assert run.total_gross == 50000
    assert run.total_deductions == 200
    assert run.total_net_pay == 49800

    line_items = db.query(PayrollLineItem).filter_by(payroll_run_id=run.id).all()
    assert len(line_items) == 1
    assert line_items[0].net_pay == 49800
    assert len(line_items[0].components) == 2  # Basic Pay (earning) + Professional Tax (deduction)
    db.close()


def test_running_payroll_twice_for_same_period_is_blocked(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)
    _submit_attendance(client, csrf_token, employee_id, "2026-07")

    client.post("/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"})

    response = client.post(
        "/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"}, follow_redirects=True
    )
    assert "already been processed" in response.text

    db = SessionLocal()
    assert db.query(PayrollRun).count() == 1  # still just the one run, not two
    db.close()


def test_payroll_run_rolls_back_completely_on_mid_run_failure(logged_in_client, monkeypatch):
    """
    Directly verifies the Implementation Plan's exit criteria for this
    phase: "an injected failure mid-run leaves no partial data." Simulates
    a crash after the PayrollRun header and first line item would already
    have been flushed to the DB (but not committed), and confirms nothing
    -- not even that partial data -- survives.
    """
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)
    _submit_attendance(client, csrf_token, employee_id, "2026-07")

    import app.services.payroll_service as payroll_service_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-run")

    monkeypatch.setattr(payroll_service_module, "PayrollLineItemComponent", _boom)

    response = client.post(
        "/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"}, follow_redirects=True
    )
    assert "unexpected error" in response.text
    assert "No changes were made" in response.text

    db = SessionLocal()
    assert db.query(PayrollRun).count() == 0  # not even the PayrollRun header persisted
    assert db.query(PayrollLineItem).count() == 0
    db.close()


def test_payroll_summary_page_shows_line_items(logged_in_client):
    client, csrf_token = logged_in_client
    employee_id = _create_employee(client, csrf_token)
    _submit_attendance(client, csrf_token, employee_id, "2026-07")
    client.post("/payroll/run", data={"csrf_token": csrf_token, "period": "2026-07"})

    db = SessionLocal()
    run = db.query(PayrollRun).first()
    run_id = run.id
    db.close()

    response = client.get(f"/payroll/{run_id}")
    assert response.status_code == 200
    assert "Test Employee" in response.text
    assert "49,800.00" in response.text


def test_payroll_summary_404_for_unknown_run(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/payroll/9999")
    assert response.status_code == 404
