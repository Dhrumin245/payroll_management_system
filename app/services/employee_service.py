"""
Employee creation/update logic, kept separate from the router so it's
testable without going through HTTP (TRD §2's layered architecture).
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Employee, EmployeeBankDetails, SalaryComponent, SalaryStructure

_CODE_PATTERN = re.compile(r"^EMP(\d+)$")


def suggest_employee_code(db: Session) -> str:
    """Sequential EMP0001, EMP0002, ... based on the highest existing numeric suffix."""
    max_num = 0
    for (code,) in db.query(Employee.employee_code).all():
        match = _CODE_PATTERN.match(code or "")
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"EMP{max_num + 1:04d}"


@dataclass
class EmployeeFormData:
    """Parsed (not yet necessarily valid) submission from the Add/Edit Employee form."""

    full_name: str = ""
    employee_code: str = ""
    designation: str = ""
    joining_date: str = ""
    email: str = ""
    phone: str = ""
    account_holder_name: str = ""
    account_number: str = ""
    ifsc_code: str = ""
    bank_name: str = ""
    basic_pay: str = ""
    hra: str = ""
    conveyance_allowance: str = ""
    component_types: list = field(default_factory=list)
    component_names: list = field(default_factory=list)
    component_amounts: list = field(default_factory=list)


def field_values_from_employee(employee: Optional[Employee], suggested_code: str = "") -> dict:
    """Values to pre-fill the form with when rendering Add (employee=None) or Edit."""
    if employee is None:
        return {
            "full_name": "",
            "employee_code": suggested_code,
            "designation": "",
            "joining_date": "",
            "email": "",
            "phone": "",
            "account_holder_name": "",
            "account_number": "",
            "ifsc_code": "",
            "bank_name": "",
            "basic_pay": "",
            "hra": "0",
            "conveyance_allowance": "0",
        }
    bank = employee.bank_details
    salary = employee.salary_structure
    return {
        "full_name": employee.full_name,
        "employee_code": employee.employee_code,
        "designation": employee.designation,
        "joining_date": employee.joining_date.isoformat(),
        "email": employee.email or "",
        "phone": employee.phone or "",
        "account_holder_name": bank.account_holder_name if bank else "",
        # Deliberately never pre-filled with the real (decrypted) number --
        # see the account_number_last4 hint used separately in the template.
        "account_number": "",
        "ifsc_code": bank.ifsc_code if bank else "",
        "bank_name": bank.bank_name if bank else "",
        "basic_pay": str(salary.basic_pay) if salary else "",
        "hra": str(salary.hra) if salary else "0",
        "conveyance_allowance": str(salary.conveyance_allowance) if salary else "0",
    }


def field_values_from_form_data(data: EmployeeFormData) -> dict:
    """Values to re-fill the form with after a validation error -- exactly what was submitted."""
    return {
        "full_name": data.full_name,
        "employee_code": data.employee_code,
        "designation": data.designation,
        "joining_date": data.joining_date,
        "email": data.email,
        "phone": data.phone,
        "account_holder_name": data.account_holder_name,
        "account_number": data.account_number,
        "ifsc_code": data.ifsc_code,
        "bank_name": data.bank_name,
        "basic_pay": data.basic_pay,
        "hra": data.hra,
        "conveyance_allowance": data.conveyance_allowance,
    }


def existing_components_for_template(employee: Optional[Employee]) -> list:
    if employee is None or employee.salary_structure is None:
        return []
    return [(c.component_type, c.name, str(c.amount)) for c in employee.salary_structure.components]


def components_from_submission(data: EmployeeFormData) -> list:
    return list(zip(data.component_types, data.component_names, data.component_amounts))


def _parse_decimal(value: str, field_name: str, errors: dict, allow_blank_as_zero: bool = False) -> Optional[Decimal]:
    value = (value or "").strip()
    if not value:
        if allow_blank_as_zero:
            return Decimal("0")
        errors[field_name] = "This field is required."
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        errors[field_name] = "Enter a valid number."
        return None
    if parsed < 0:
        errors[field_name] = "Must be zero or greater."
        return None
    return parsed


def validate_employee_form(db: Session, data: EmployeeFormData, existing_employee_id: Optional[int] = None) -> dict:
    """Returns a dict of field -> error message. Empty dict means valid."""
    errors: dict = {}

    if not data.full_name.strip():
        errors["full_name"] = "Full name is required."
    if not data.designation.strip():
        errors["designation"] = "Designation is required."

    if not data.employee_code.strip():
        errors["employee_code"] = "Employee code is required."
    else:
        query = db.query(Employee).filter(Employee.employee_code == data.employee_code.strip())
        if existing_employee_id is not None:
            query = query.filter(Employee.id != existing_employee_id)
        if query.first():
            errors["employee_code"] = "Employee code already exists."

    try:
        datetime.strptime(data.joining_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        errors["joining_date"] = "Enter a valid joining date."

    basic_pay = _parse_decimal(data.basic_pay, "basic_pay", errors)
    if basic_pay is not None and basic_pay <= 0:
        errors["basic_pay"] = "Basic pay must be greater than 0."

    _parse_decimal(data.hra, "hra", errors, allow_blank_as_zero=True)
    _parse_decimal(data.conveyance_allowance, "conveyance_allowance", errors, allow_blank_as_zero=True)

    # A new/changed account number always needs a holder name. Leaving the
    # account number blank (to keep an existing one unchanged, in edit mode)
    # while still editing the holder name is fine and doesn't error.
    if data.account_number.strip() and not data.account_holder_name.strip():
        errors["account_holder_name"] = "Account holder name is required when providing an account number."

    for i, (ctype, cname, camount) in enumerate(
        zip(data.component_types, data.component_names, data.component_amounts)
    ):
        if not cname.strip():
            continue  # a blank row (e.g. added then left empty) is silently skipped, not an error
        if ctype not in ("allowance", "deduction"):
            errors[f"component_{i}_type"] = "Invalid component type."
        _parse_decimal(camount, f"component_{i}_amount", errors)

    return errors


def save_employee(db: Session, data: EmployeeFormData, employee: Optional[Employee] = None) -> Employee:
    """
    Creates a new employee or updates an existing one. Caller must have
    already validated via validate_employee_form(). Salary components are
    fully replaced on every save (deleted and re-inserted) rather than
    diffed in place -- simpler and correct, since the form doesn't track
    individual component IDs.
    """
    joining_date = datetime.strptime(data.joining_date, "%Y-%m-%d").date()

    if employee is None:
        employee = Employee(status="active")
        db.add(employee)

    employee.full_name = data.full_name.strip()
    employee.employee_code = data.employee_code.strip()
    employee.designation = data.designation.strip()
    employee.joining_date = joining_date
    employee.email = data.email.strip() or None
    employee.phone = data.phone.strip() or None
    db.flush()  # ensures employee.id exists for the dependent rows below

    if data.account_number.strip():
        # A new/changed account number was submitted -- create or update.
        bank_details = employee.bank_details or EmployeeBankDetails(employee_id=employee.id)
        bank_details.account_holder_name = data.account_holder_name.strip()
        bank_details.account_number = data.account_number.strip()  # encrypts via the model property
        bank_details.ifsc_code = data.ifsc_code.strip() or None
        bank_details.bank_name = data.bank_name.strip() or None
        db.add(bank_details)
    elif data.account_holder_name.strip() and employee.bank_details:
        # Account number left blank on purpose (edit mode, keep it
        # unchanged) but other bank fields were edited.
        employee.bank_details.account_holder_name = data.account_holder_name.strip()
        employee.bank_details.ifsc_code = data.ifsc_code.strip() or None
        employee.bank_details.bank_name = data.bank_name.strip() or None

    salary_structure = employee.salary_structure
    if salary_structure is None:
        salary_structure = SalaryStructure(employee_id=employee.id)
        db.add(salary_structure)
    salary_structure.basic_pay = Decimal(data.basic_pay)
    salary_structure.hra = Decimal(data.hra or "0")
    salary_structure.conveyance_allowance = Decimal(data.conveyance_allowance or "0")
    db.flush()

    for existing in list(salary_structure.components):
        db.delete(existing)
    db.flush()

    for ctype, cname, camount in zip(data.component_types, data.component_names, data.component_amounts):
        if not cname.strip():
            continue
        db.add(
            SalaryComponent(
                salary_structure_id=salary_structure.id,
                component_type=ctype,
                name=cname.strip(),
                amount=Decimal(camount),
            )
        )

    db.commit()
    db.refresh(employee)
    return employee
