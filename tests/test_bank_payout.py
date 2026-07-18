"""
Tests for Phase 13 Bank Payout File.
"""
import csv
import io
from decimal import Decimal
from datetime import date
import pytest

from app.dependencies import SessionLocal
from app.models import Employee, EmployeeBankDetails, PayrollLineItem, PayrollRun
from app.services.bank_payout_service import generate_neft_csv


def test_generate_neft_csv_with_bank_details(client):
    db = SessionLocal()

    # Create test employee
    emp1 = Employee(
        employee_code="EMP9001",
        full_name="Alice Smith",
        designation="Designer",
        joining_date=date(2024, 1, 1),
        status="active",
        email="alice@test.com",
    )
    db.add(emp1)
    db.flush()

    # Create bank details for Alice
    bank1 = EmployeeBankDetails(
        employee_id=emp1.id,
        account_holder_name="Alice Smith",
        ifsc_code="HDFC0001234",
        bank_name="HDFC Bank",
    )
    # This invokes the setter which transparently encrypts
    bank1.account_number = "1234567890"
    db.add(bank1)

    # Create test employee without bank details
    emp2 = Employee(
        employee_code="EMP9002",
        full_name="Bob Jones",
        designation="Manager",
        joining_date=date(2024, 1, 1),
        status="active",
        email="bob@test.com",
    )
    db.add(emp2)
    db.flush()

    db.commit()

    # Create fake PayrollLineItems
    item1 = PayrollLineItem(
        payroll_run_id=1,
        employee_id=emp1.id,
        employee_code_snapshot="EMP9001",
        employee_name_snapshot="Alice Smith",
        days_present_snapshot=Decimal("20.00"),
        days_on_leave_snapshot=Decimal("0.00"),
        gross_pay=Decimal("50000.00"),
        total_deductions=Decimal("2000.00"),
        net_pay=Decimal("48000.00"),
    )
    item2 = PayrollLineItem(
        payroll_run_id=1,
        employee_id=emp2.id,
        employee_code_snapshot="EMP9002",
        employee_name_snapshot="Bob Jones",
        days_present_snapshot=Decimal("20.00"),
        days_on_leave_snapshot=Decimal("0.00"),
        gross_pay=Decimal("60000.00"),
        total_deductions=Decimal("3000.00"),
        net_pay=Decimal("57000.00"),
    )

    # Set temporary relationships for the test
    item1.employee = emp1
    item2.employee = emp2

    # Generate CSV
    csv_bytes = generate_neft_csv([item1, item2])
    csv_text = csv_bytes.decode("utf-8")

    # Read and parse CSV
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Assert header
    assert rows[0] == [
        "Employee Code",
        "Employee Name",
        "Account Holder Name",
        "Account Number",
        "IFSC Code",
        "Bank Name",
        "Net Pay",
    ]

    # Assert Alice's row (with bank details decrypted)
    assert rows[1] == [
        "EMP9001",
        "Alice Smith",
        "Alice Smith",
        "1234567890",
        "HDFC0001234",
        "HDFC Bank",
        "48000.00",
    ]

    # Assert Bob's row (empty bank details)
    assert rows[2] == [
        "EMP9002",
        "Bob Jones",
        "",
        "",
        "",
        "",
        "57000.00",
    ]

    db.close()


def test_download_bank_payout_file_route(logged_in_client):
    client, csrf_token = logged_in_client
    db = SessionLocal()

    # Seed run
    run = PayrollRun(
        id=101,
        period=date(2024, 2, 1),
        status="completed",
        total_gross=Decimal("110000.00"),
        total_deductions=Decimal("5000.00"),
        total_net_pay=Decimal("105000.00"),
        employee_count=2,
        run_by_user_id=1,
    )
    db.add(run)
    db.flush()

    emp = Employee(
        employee_code="EMP101",
        full_name="Alice Summary",
        designation="Lead",
        joining_date=date(2024, 1, 1),
        status="active",
    )
    db.add(emp)
    db.flush()

    # Alice bank details
    bank = EmployeeBankDetails(
        employee_id=emp.id,
        account_holder_name="Alice Summary",
        ifsc_code="ICIC0009999",
        bank_name="ICICI Bank",
    )
    bank.account_number = "9876543210"
    db.add(bank)

    item = PayrollLineItem(
        payroll_run_id=run.id,
        employee_id=emp.id,
        employee_code_snapshot="EMP101",
        employee_name_snapshot="Alice Summary",
        days_present_snapshot=Decimal("22.00"),
        days_on_leave_snapshot=Decimal("0.00"),
        gross_pay=Decimal("50000.00"),
        total_deductions=Decimal("1000.00"),
        net_pay=Decimal("49000.00"),
    )
    db.add(item)
    db.commit()

    # GET /payroll/{run_id}/bank-file
    res = client.get(f"/payroll/{run.id}/bank-file")
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=\"bank_payout_2024-02.csv\"" in res.headers["content-disposition"]

    # Parse response content
    reader = csv.reader(io.StringIO(res.text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[1] == [
        "EMP101",
        "Alice Summary",
        "Alice Summary",
        "9876543210",
        "ICIC0009999",
        "ICICI Bank",
        "49000.00",
    ]

    db.close()
