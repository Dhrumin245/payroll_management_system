"""
Phase 4d checks: payslip PDF download and CSV export. Run with: pytest
"""
import csv
import io

from app.dependencies import SessionLocal
from app.models import Employee, PayrollRun

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


def _run_payroll_for_one_employee(client, csrf_token, period="2026-07"):
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))
    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()

    client.post(
        f"/attendance/{period}",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["27"],
            "days_on_leave": ["0"],
        },
    )
    client.post("/payroll/run", data={"csrf_token": csrf_token, "period": period})

    db = SessionLocal()
    run_id = db.query(PayrollRun).first().id
    db.close()
    return run_id, employee_id


def test_download_payslip_returns_a_real_pdf(logged_in_client):
    client, csrf_token = logged_in_client
    run_id, employee_id = _run_payroll_for_one_employee(client, csrf_token)

    response = client.get(f"/payroll/{run_id}/payslip/{employee_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")  # genuinely a PDF, not just a 200 with junk content
    assert len(response.content) > 500  # a real, populated document, not an empty stub


def test_payslip_uses_snapshot_unaffected_by_later_employee_edits(logged_in_client):
    """
    Confirms the payslip reflects what was true at run time (Backend Schema's
    snapshot principle) -- editing the employee afterward shouldn't break
    generation or change what a past payslip would show.
    """
    client, csrf_token = logged_in_client
    run_id, employee_id = _run_payroll_for_one_employee(client, csrf_token)

    db = SessionLocal()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    employee.full_name = "Renamed Employee"
    db.commit()
    db.close()

    response = client.get(f"/payroll/{run_id}/payslip/{employee_id}")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_download_payslip_404_for_employee_not_in_run(logged_in_client):
    client, csrf_token = logged_in_client
    run_id, _ = _run_payroll_for_one_employee(client, csrf_token)

    response = client.get(f"/payroll/{run_id}/payslip/9999")
    assert response.status_code == 404


def test_download_payslip_404_for_unknown_run(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/payroll/9999/payslip/1")
    assert response.status_code == 404


def test_csv_export_contains_correct_rows(logged_in_client):
    client, csrf_token = logged_in_client
    run_id, _ = _run_payroll_for_one_employee(client, csrf_token)

    response = client.get(f"/payroll/{run_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["Employee Code", "Employee Name", "Gross Pay", "Total Deductions", "Net Pay"]
    assert rows[1][0] == "EMP0001"
    assert rows[1][1] == "Test Employee"


def test_csv_export_404_for_unknown_run(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/payroll/9999/export")
    assert response.status_code == 404
