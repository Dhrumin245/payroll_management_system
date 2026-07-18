"""
Tests for Phase 14 Excel Export Service and Routes.
"""
from datetime import date
from decimal import Decimal
import io
import pytest
from openpyxl import load_workbook

from app.dependencies import SessionLocal
from app.models import Employee, PayrollLineItem, PayrollRun, User
from app.services.excel_export_service import generate_payroll_excel
from tests.test_rbac import _seed_user, _login


def test_excel_export_generation(client):
    db = SessionLocal()
    try:
        # Seed user for foreign key check
        user = User(username="xl_test_user", password_hash="hash", role="admin")
        db.add(user)
        db.flush()

        # Create test employee
        emp = Employee(
            employee_code="EMP_XL",
            full_name="Excel Tester",
            designation="Tester",
            joining_date=date(2024, 1, 1),
            status="active",
        )
        db.add(emp)
        db.flush()

        # Create payroll run
        run = PayrollRun(
            id=301,
            period=date(2024, 3, 1),
            status="completed",
            total_gross=Decimal("75000.00"),
            total_deductions=Decimal("5000.00"),
            total_net_pay=Decimal("70000.00"),
            employee_count=1,
            run_by_user_id=user.id,
        )
        db.add(run)
        db.flush()

        # Create line item
        item = PayrollLineItem(
            payroll_run_id=run.id,
            employee_id=emp.id,
            employee_code_snapshot="EMP_XL",
            employee_name_snapshot="Excel Tester",
            days_present_snapshot=Decimal("22.00"),
            days_on_leave_snapshot=Decimal("1.00"),
            gross_pay=Decimal("75000.00"),
            total_deductions=Decimal("5000.00"),
            net_pay=Decimal("70000.00"),
        )
        db.add(item)
        db.flush()

        # Seed component
        from app.models.payroll import PayrollLineItemComponent
        c1 = PayrollLineItemComponent(
            payroll_line_item_id=item.id,
            name="Basic Salary",
            amount=Decimal("75000.00"),
            component_type="earning",
        )
        c2 = PayrollLineItemComponent(
            payroll_line_item_id=item.id,
            name="Provident Fund (PF)",
            amount=Decimal("5000.00"),
            component_type="deduction",
        )
        db.add_all([c1, c2])
        db.commit()

        # Generate excel bytes
        excel_bytes = generate_payroll_excel(run, [item])
        assert isinstance(excel_bytes, bytes)

        # Load workbook and verify sheets
        wb = load_workbook(io.BytesIO(excel_bytes))
        assert "Summary" in wb.sheetnames
        assert "Employee Breakdown" in wb.sheetnames
        assert "Statutory Summary" in wb.sheetnames

        # Verify Summary content
        ws_summary = wb["Summary"]
        assert "Payroll Summary — March 2024" in ws_summary["A1"].value

        # Verify Breakdown columns
        ws_breakdown = wb["Employee Breakdown"]
        row1_vals = [cell.value for cell in ws_breakdown[1]]
        assert "Employee Code" in row1_vals
        assert "Basic Salary" in row1_vals
        assert "Provident Fund (PF)" in row1_vals

        row2_vals = [cell.value for cell in ws_breakdown[2]]
        assert "EMP_XL" in row2_vals
        assert "Excel Tester" in row2_vals

    finally:
        db.close()


def test_excel_export_route_and_rbac(client):
    # Seed users
    admin_user, admin_pass = _seed_user("admin", "xl_admin")
    mgr_user, mgr_pass = _seed_user("manager", "xl_mgr")
    emp_user, emp_pass = _seed_user("employee", "xl_emp")

    # Seed run database entry
    db = SessionLocal()
    try:
        admin_db_user = db.query(User).filter(User.username == "xl_admin").first()
        run = PayrollRun(
            id=302,
            period=date(2024, 4, 1),
            status="completed",
            total_gross=Decimal("50000.00"),
            total_deductions=Decimal("0.00"),
            total_net_pay=Decimal("50000.00"),
            employee_count=0,
            run_by_user_id=admin_db_user.id,
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    # 1. Admin download
    _login(client, admin_user, admin_pass)
    resp = client.get("/payroll/302/export-excel")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=\"payroll_2024-04.xlsx\"" in resp.headers["content-disposition"]

    # 2. Manager download
    _login(client, mgr_user, mgr_pass)
    resp = client.get("/payroll/302/export-excel")
    assert resp.status_code == 200

    # 3. Employee download should be denied
    _login(client, emp_user, emp_pass)
    resp = client.get("/payroll/302/export-excel")
    assert resp.status_code == 403

    # 4. Non-existent run ID should yield 404 for admin
    _login(client, admin_user, admin_pass)
    resp = client.get("/payroll/9999/export-excel")
    assert resp.status_code == 404
