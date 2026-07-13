"""
Phase 4a checks: employee CRUD, search/filter empty states, validation, and
deactivate/reactivate. Run with: pytest
"""
from app.dependencies import SessionLocal
from app.models import Employee

_VALID_EMPLOYEE_PAYLOAD = {
    "full_name": "Test Employee",
    "employee_code": "EMP0001",
    "designation": "Engineer",
    "joining_date": "2026-01-01",
    "basic_pay": "50000",
    "hra": "20000",
    "conveyance_allowance": "2000",
    "account_holder_name": "Test Employee",
    "account_number": "1234567890",
    "component_type": ["deduction"],
    "component_name": ["Provident Fund"],
    "component_amount": ["6000"],
}


def test_employee_list_shows_empty_state_when_no_employees(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/employees")
    assert response.status_code == 200
    assert "haven't added any employees yet" in response.text


def test_create_employee_success(logged_in_client):
    client, csrf_token = logged_in_client
    payload = dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token)

    response = client.post("/employees/new", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert "Employee added successfully" in response.text

    db = SessionLocal()
    employee = db.query(Employee).filter(Employee.employee_code == "EMP0001").first()
    assert employee is not None
    assert employee.salary_structure.basic_pay == 50000
    assert len(employee.salary_structure.components) == 1
    assert employee.bank_details.account_number_last4 == "7890"
    assert employee.bank_details.account_number == "1234567890"  # decrypts correctly
    db.close()


def test_create_employee_duplicate_code_shows_error(logged_in_client):
    client, csrf_token = logged_in_client
    payload = dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token)
    client.post("/employees/new", data=payload)

    payload["full_name"] = "Second Employee"
    response = client.post("/employees/new", data=payload)
    assert response.status_code == 400
    assert "already exists" in response.text


def test_create_employee_requires_positive_basic_pay(logged_in_client):
    client, csrf_token = logged_in_client
    payload = dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token, basic_pay="0")

    response = client.post("/employees/new", data=payload)
    assert response.status_code == 400
    assert "greater than 0" in response.text


def test_create_employee_missing_required_field_shows_error(logged_in_client):
    client, csrf_token = logged_in_client
    payload = dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token, full_name="")

    response = client.post("/employees/new", data=payload)
    assert response.status_code == 400
    assert "Full name is required" in response.text


def test_deactivate_and_reactivate_employee(logged_in_client):
    client, csrf_token = logged_in_client
    client.post("/employees/new", data=dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))

    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()

    client.post(f"/employees/{employee_id}/deactivate", data={"csrf_token": csrf_token})
    db = SessionLocal()
    assert db.query(Employee).filter(Employee.id == employee_id).first().status == "inactive"
    db.close()

    client.post(f"/employees/{employee_id}/reactivate", data={"csrf_token": csrf_token})
    db = SessionLocal()
    assert db.query(Employee).filter(Employee.id == employee_id).first().status == "active"
    db.close()


def test_employee_detail_404_for_unknown_id(logged_in_client):
    client, _ = logged_in_client
    response = client.get("/employees/9999")
    assert response.status_code == 404
    assert "Page not found" in response.text


def test_edit_employee_keeps_bank_account_unchanged_when_left_blank(logged_in_client):
    client, csrf_token = logged_in_client
    client.post("/employees/new", data=dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))

    db = SessionLocal()
    employee = db.query(Employee).filter(Employee.employee_code == "EMP0001").first()
    employee_id = employee.id
    original_account_number = employee.bank_details.account_number
    db.close()

    edit_payload = dict(_VALID_EMPLOYEE_PAYLOAD, csrf_token=csrf_token, designation="Senior Engineer")
    edit_payload["account_number"] = ""  # left blank on purpose -- should NOT clear the existing account
    client.post(f"/employees/{employee_id}", data=edit_payload)

    db = SessionLocal()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    assert employee.designation == "Senior Engineer"
    assert employee.bank_details.account_number == original_account_number
    db.close()
