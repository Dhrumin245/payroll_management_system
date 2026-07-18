"""
Phase 11: Salary Revision History & Variable Pay tests.
"""
from datetime import date, datetime
from decimal import Decimal
import pytest

from app.dependencies import SessionLocal
from app.models import Employee, SalaryStructure, SalaryStructureHistory, VariablePayItem, AttendanceRecord
from app.services.employee_service import EmployeeFormData, save_employee
from app.services.salary_history_service import (
    get_salary_history,
    get_variable_pay_for_period,
    upsert_variable_pay,
)
from app.services.payroll_service import run_payroll
from tests.conftest import extract_csrf_token

_emp_counter = 0

def _seed_employee_with_salary(db) -> Employee:
    global _emp_counter
    _emp_counter += 1
    code = f"EMP{6000 + _emp_counter:04d}"
    
    emp = Employee(
        employee_code=code,
        full_name="History Tester",
        designation="Tester",
        joining_date=date(2024, 1, 1),
        status="active"
    )
    db.add(emp)
    db.flush()
    
    struct = SalaryStructure(
        employee_id=emp.id,
        basic_pay=Decimal("50000.00"),
        hra=Decimal("20000.00"),
        conveyance_allowance=Decimal("1600.00"),
        effective_from=date(2024, 1, 1)
    )
    db.add(struct)
    db.commit()
    db.refresh(emp)
    return emp


def test_salary_edit_creates_snapshot(client, logged_in_client):
    db = SessionLocal()
    emp = _seed_employee_with_salary(db)
    
    # Verify no history exists yet
    assert len(get_salary_history(db, emp.id)) == 0
    
    # Edit salary structure via save_employee
    data = EmployeeFormData(
        full_name=emp.full_name,
        employee_code=emp.employee_code,
        designation=emp.designation,
        joining_date=emp.joining_date.isoformat(),
        basic_pay="60000.00",
        hra="24000.00",
        conveyance_allowance="2000.00",
    )
    
    # Perform update (with admin user id)
    c, csrf = logged_in_client
    save_employee(db, data, employee=emp, user_id=1)
    
    # Retrieve history
    history = get_salary_history(db, emp.id)
    assert len(history) == 1
    
    snapshot = history[0]
    assert snapshot.basic_pay == Decimal("50000.00")
    assert snapshot.hra == Decimal("20000.00")
    assert snapshot.conveyance_allowance == Decimal("1600.00")
    assert snapshot.effective_from == date(2024, 1, 1)
    assert snapshot.superseded_at is not None
    
    # Current salary structure should have the new effective_from
    db.refresh(emp)
    assert emp.salary_structure.basic_pay == Decimal("60000.00")
    assert emp.salary_structure.effective_from == date.today()
    db.close()


def test_no_salary_change_no_snapshot(client, logged_in_client):
    db = SessionLocal()
    emp = _seed_employee_with_salary(db)
    
    # Edit non-salary fields
    data = EmployeeFormData(
        full_name="New Name",
        employee_code=emp.employee_code,
        designation="New Designation",
        joining_date=emp.joining_date.isoformat(),
        basic_pay="50000.00",
        hra="20000.00",
        conveyance_allowance="1600.00",
    )
    
    save_employee(db, data, employee=emp, user_id=1)
    
    # Verify no snapshot was created since values are identical
    history = get_salary_history(db, emp.id)
    assert len(history) == 0
    db.close()


def test_variable_pay_crud_and_payroll_integration(client, logged_in_client):
    db = SessionLocal()
    emp = _seed_employee_with_salary(db)
    
    period = date(2025, 6, 1)
    
    # Set variable pay items
    items = [
        {"component_type": "earning", "name": "Project Bonus", "amount": "5000.00"},
        {"component_type": "deduction", "name": "Equipment Damage", "amount": "1500.00"},
    ]
    upsert_variable_pay(db, emp.id, period, items, created_by_user_id=1)
    db.commit()
    
    # Verify get_variable_pay_for_period
    db_items = get_variable_pay_for_period(db, emp.id, period)
    assert len(db_items) == 2
    assert db_items[0].name == "Equipment Damage"
    assert db_items[0].component_type == "deduction"
    assert db_items[0].amount == Decimal("1500.00")
    
    # Add attendance so we can run payroll
    att = AttendanceRecord(
        employee_id=emp.id,
        period=period,
        days_present=Decimal("25.0"),
        days_on_leave=Decimal("0.0"),
        total_working_days=Decimal("25.0"),
    )
    db.add(att)
    db.commit()
    
    # Run payroll
    run = run_payroll(db, period, run_by_user_id=1)
    
    # Verify the line item and its components
    line_item = run.line_items[0]
    # Earnings: Basic(50000) + HRA(20000) + Conveyance(1600) + Project Bonus(5000) = 76600
    # Deductions: Equipment Damage(1500)
    # Net: 76600 - 1500 = 75100
    assert line_item.gross_pay == Decimal("76600.00")
    assert line_item.total_deductions == Decimal("1500.00")
    assert line_item.net_pay == Decimal("75100.00")
    
    # Check components
    comp_names = [c.name for c in line_item.components]
    assert "Project Bonus" in comp_names
    assert "Equipment Damage" in comp_names
    db.close()


def test_variable_pay_web_endpoints(client, logged_in_client):
    db = SessionLocal()
    emp = _seed_employee_with_salary(db)
    db.close()
    
    c, csrf = logged_in_client
    
    # Hit GET endpoint
    resp = c.get(f"/employees/{emp.id}/variable-pay?period=2025-06")
    assert resp.status_code == 200
    assert "Variable Pay" in resp.text
    
    # Post updates
    post_resp = c.post(
        f"/employees/{emp.id}/variable-pay",
        data={
            "period": "2025-06",
            "item_type": ["earning", "deduction"],
            "item_name": ["Referral Bonus", "Loss of Laptop"],
            "item_amount": ["10000.00", "2000.00"],
            "csrf_token": csrf,
        },
        follow_redirects=True
    )
    assert post_resp.status_code == 200
    assert "updated successfully" in post_resp.text
    
    # Verify db items
    db = SessionLocal()
    items = get_variable_pay_for_period(db, emp.id, date(2025, 6, 1))
    assert len(items) == 2
    db.close()
