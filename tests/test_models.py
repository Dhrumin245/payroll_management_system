"""
Phase 2 checks: schema constraints, relationships, and cascade/restrict
behavior actually work as designed (Backend Schema §3, §7). Run with: pytest

Runs against a dedicated test.db (see tests/conftest.py), never the real
dev database.
"""
from datetime import date

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError

from app.dependencies import SessionLocal, engine
from app.models import (
    AttendanceRecord,
    Base,
    Employee,
    EmployeeBankDetails,
    PayrollLineItem,
    PayrollRun,
    SalaryStructure,
    User,
)
from app.services.security import hash_password


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_employee(db, code: str = "EMP0001") -> Employee:
    employee = Employee(
        employee_code=code,
        full_name="Test Employee",
        designation="Engineer",
        joining_date=date(2026, 1, 1),
        status="active",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def test_employee_code_must_be_unique(db):
    _make_employee(db, code="EMP0001")
    db.add(
        Employee(
            employee_code="EMP0001",
            full_name="Someone Else",
            designation="Engineer",
            joining_date=date(2026, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_attendance_unique_per_employee_per_period(db):
    employee = _make_employee(db)
    db.add(
        AttendanceRecord(
            employee_id=employee.id, period=date(2026, 7, 1), days_present=20, days_on_leave=0, total_working_days=22
        )
    )
    db.commit()

    db.add(
        AttendanceRecord(
            employee_id=employee.id, period=date(2026, 7, 1), days_present=18, days_on_leave=2, total_working_days=22
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_attendance_days_cannot_exceed_working_days(db):
    employee = _make_employee(db)
    db.add(
        AttendanceRecord(
            employee_id=employee.id, period=date(2026, 7, 1), days_present=25, days_on_leave=2, total_working_days=22
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_employee_with_payroll_history_is_blocked(db):
    """The core Backend Schema §7 guarantee: RESTRICT, enforced by the DB itself."""
    employee = _make_employee(db)
    admin = User(username="admin", password_hash=hash_password("x"), role="admin")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    run = PayrollRun(
        period=date(2026, 7, 1),
        status="completed",
        total_gross=50000,
        total_deductions=5000,
        total_net_pay=45000,
        employee_count=1,
        run_by_user_id=admin.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    db.add(
        PayrollLineItem(
            payroll_run_id=run.id,
            employee_id=employee.id,
            employee_code_snapshot=employee.employee_code,
            employee_name_snapshot=employee.full_name,
            days_present_snapshot=22,
            days_on_leave_snapshot=0,
            gross_pay=50000,
            total_deductions=5000,
            net_pay=45000,
        )
    )
    db.commit()

    db.delete(employee)
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_employee_without_payroll_history_cascades(db):
    employee = _make_employee(db)
    db.add(SalaryStructure(employee_id=employee.id, basic_pay=50000, hra=20000, conveyance_allowance=2000))
    db.commit()

    db.delete(employee)
    db.commit()  # should succeed -- no payroll history, cascade removes the salary structure too

    assert db.query(SalaryStructure).filter_by(employee_id=employee.id).first() is None


def test_bank_account_number_round_trips_through_encryption(db, monkeypatch):
    monkeypatch.setattr("app.config.settings.BANK_ENCRYPTION_KEY", Fernet.generate_key().decode())

    employee = _make_employee(db)
    bank_details = EmployeeBankDetails(employee_id=employee.id, account_holder_name="Test Employee")
    bank_details.account_number = "1234567890"
    db.add(bank_details)
    db.commit()
    db.refresh(bank_details)

    assert bank_details.account_number_last4 == "7890"
    assert bank_details.account_number_encrypted != "1234567890"  # never stored in plaintext
    assert bank_details.account_number == "1234567890"  # decrypts correctly on read
