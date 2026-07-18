"""
CLI commands for local/admin operations.

Run with:
    python -m app.cli create-admin
    python -m app.cli seed-demo

There's no signup flow anywhere in this app by design (Backend Schema §6) —
create-admin is the only way an admin account gets created.
"""
import getpass
from datetime import date
from decimal import Decimal

import typer

from app.dependencies import SessionLocal
from app.models import Employee, EmployeeBankDetails, SalaryComponent, SalaryStructure, User
from app.services.security import hash_password

cli = typer.Typer()


@cli.command("create-admin")
def create_admin(username: str = typer.Option(..., prompt=True)) -> None:
    """Seed the first admin user."""
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        typer.echo("Passwords do not match.")
        raise typer.Exit(code=1)
    if not password:
        typer.echo("Password cannot be empty.")
        raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            typer.echo(f"A user named '{username}' already exists.")
            raise typer.Exit(code=1)

        user = User(username=username, password_hash=hash_password(password), role="admin")
        db.add(user)
        db.commit()
        typer.echo(f"Admin user '{username}' created.")
    finally:
        db.close()


@cli.command("create-manager")
def create_manager(username: str = typer.Option(..., prompt=True)) -> None:
    """Create a payroll-manager user account (role='manager').

    Managers can view/edit employees and enter attendance, but cannot
    trigger payroll runs (admin-only).
    """
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        typer.echo("Passwords do not match.")
        raise typer.Exit(code=1)
    if not password:
        typer.echo("Password cannot be empty.")
        raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            typer.echo(f"A user named '{username}' already exists.")
            raise typer.Exit(code=1)

        user = User(username=username, password_hash=hash_password(password), role="manager")
        db.add(user)
        db.commit()
        typer.echo(f"Manager user '{username}' created.")
    finally:
        db.close()


@cli.command("link-employee")
def link_employee(
    username: str = typer.Option(..., prompt=True),
    employee_code: str = typer.Option(..., prompt=True),
) -> None:
    """Link an existing employee record to a User account for self-service login.

    Sets the user's role to 'employee' and assigns their employee_id.
    If the user does not exist yet, a new one is created (password is prompted).
    """
    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.employee_code == employee_code).first()
        if employee is None:
            typer.echo(f"No employee found with code '{employee_code}'.")
            raise typer.Exit(code=1)

        user = db.query(User).filter(User.username == username).first()
        if user is None:
            password = getpass.getpass(f"Password for new user '{username}': ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                typer.echo("Passwords do not match.")
                raise typer.Exit(code=1)
            if not password:
                typer.echo("Password cannot be empty.")
                raise typer.Exit(code=1)
            user = User(username=username, password_hash=hash_password(password), role="employee")
            db.add(user)
            db.flush()

        user.role = "employee"
        user.employee_id = employee.id
        db.commit()
        typer.echo(f"User '{username}' linked to employee {employee_code} ({employee.full_name}).")
    finally:
        db.close()


# Fictional sample data only — never real employees, per the PRD's
# assumption that this is a portfolio/demo project.
_SAMPLE_EMPLOYEES = [
    {
        "employee_code": "EMP0001",
        "full_name": "Aisha Kapoor",
        "designation": "Software Engineer",
        "joining_date": date(2024, 3, 1),
        "basic_pay": Decimal("60000"),
        "hra": Decimal("24000"),
        "conveyance_allowance": Decimal("2000"),
        "account_number": "000100019876",
    },
    {
        "employee_code": "EMP0002",
        "full_name": "Rohan Mehta",
        "designation": "QA Engineer",
        "joining_date": date(2023, 11, 15),
        "basic_pay": Decimal("48000"),
        "hra": Decimal("19200"),
        "conveyance_allowance": Decimal("2000"),
        "account_number": "000100025432",
    },
    {
        "employee_code": "EMP0003",
        "full_name": "Sara Fernandes",
        "designation": "Product Designer",
        "joining_date": date(2025, 1, 10),
        "basic_pay": Decimal("55000"),
        "hra": Decimal("22000"),
        "conveyance_allowance": Decimal("2000"),
        "account_number": "000100031111",
    },
    {
        "employee_code": "EMP0004",
        "full_name": "Vikram Nair",
        "designation": "Office Administrator",
        "joining_date": date(2022, 6, 1),
        "basic_pay": Decimal("32000"),
        "hra": Decimal("12800"),
        "conveyance_allowance": Decimal("1500"),
        "account_number": "000100048765",
    },
]


@cli.command("seed-demo")
def seed_demo() -> None:
    """Populate the database with a handful of fictional sample employees for local dev/demos."""
    db = SessionLocal()
    try:
        created = 0
        for data in _SAMPLE_EMPLOYEES:
            if db.query(Employee).filter(Employee.employee_code == data["employee_code"]).first():
                continue  # already seeded, skip

            employee = Employee(
                employee_code=data["employee_code"],
                full_name=data["full_name"],
                designation=data["designation"],
                joining_date=data["joining_date"],
                status="active",
            )
            db.add(employee)
            db.flush()  # populates employee.id for the dependent rows below

            bank_details = EmployeeBankDetails(
                employee_id=employee.id,
                account_holder_name=data["full_name"],
                ifsc_code="HDFC0001234",
                bank_name="Demo Bank",
            )
            bank_details.account_number = data["account_number"]  # encrypted via the model property
            db.add(bank_details)

            salary_structure = SalaryStructure(
                employee_id=employee.id,
                basic_pay=data["basic_pay"],
                hra=data["hra"],
                conveyance_allowance=data["conveyance_allowance"],
            )
            db.add(salary_structure)
            db.flush()

            db.add(
                SalaryComponent(
                    salary_structure_id=salary_structure.id,
                    component_type="deduction",
                    name="Provident Fund",
                    amount=(data["basic_pay"] * Decimal("0.12")).quantize(Decimal("0.01")),
                )
            )
            db.add(
                SalaryComponent(
                    salary_structure_id=salary_structure.id,
                    component_type="deduction",
                    name="Professional Tax",
                    amount=Decimal("200.00"),
                )
            )
            created += 1

        db.commit()
        skipped = len(_SAMPLE_EMPLOYEES) - created
        message = f"Seeded {created} sample employee(s)."
        if skipped:
            message += f" Skipped {skipped} already present."
        typer.echo(message)
    finally:
        db.close()


if __name__ == "__main__":
    cli()
