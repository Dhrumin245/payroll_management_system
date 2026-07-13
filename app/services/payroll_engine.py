"""
Pure, framework-free payroll calculation logic (TRD §2's layered
architecture) -- this module has zero FastAPI/SQLAlchemy imports, which is
what makes it directly unit-testable without a database or web server.

This is the one module in the whole app where a bug is embarrassing rather
than just annoying, per the Implementation Plan's own risk callout for this
phase -- treat changes here with more care than anywhere else in the code.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import List

TWO_PLACES = Decimal("0.01")


@dataclass
class SalaryComponentInput:
    component_type: str  # "allowance" or "deduction"
    name: str
    amount: Decimal


@dataclass
class PayrollInput:
    """Everything the engine needs for one employee, one period."""

    employee_id: int
    employee_code: str
    employee_name: str
    basic_pay: Decimal
    hra: Decimal
    conveyance_allowance: Decimal
    components: List[SalaryComponentInput]
    days_present: Decimal
    days_on_leave: Decimal
    total_working_days: Decimal


@dataclass
class LineItemComponent:
    component_type: str  # "earning" or "deduction"
    name: str
    amount: Decimal


@dataclass
class PayrollResult:
    """Everything needed to persist one PayrollLineItem + its components."""

    employee_id: int
    employee_code: str
    employee_name: str
    days_present: Decimal
    days_on_leave: Decimal
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    line_components: List[LineItemComponent] = field(default_factory=list)


@dataclass
class PayrollRunResult:
    line_items: List[PayrollResult]
    total_gross: Decimal
    total_deductions: Decimal
    total_net_pay: Decimal
    employee_count: int


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _prorate(amount: Decimal, days_present: Decimal, total_working_days: Decimal) -> Decimal:
    """
    [Decision, from this project's missing-details discussion]: earnings
    prorate by attendance ratio (days_present / total_working_days).
    Deductions never call this function -- they apply at their full
    configured amount regardless of attendance, matching how a flat monthly
    deduction (e.g. Professional Tax) actually behaves.
    """
    if total_working_days <= 0:
        return Decimal("0.00")
    ratio = days_present / total_working_days
    return _round(amount * ratio)


def calculate_payroll_for_employee(data: PayrollInput) -> PayrollResult:
    """
    Computes gross pay (Basic + HRA + Conveyance + allowance-type
    components, each prorated by attendance), total deductions
    (deduction-type components, applied at full amount, unprorated), and
    net pay = gross - deductions.

    Note: net pay is NOT floored at zero. If deductions exceed gross pay
    (e.g. an active employee with zero attendance for the whole period),
    the result is a negative net pay, surfaced honestly rather than
    silently clamped -- clamping would hide a number that needs a human to
    look at it, not mask it. See test_zero_attendance_can_produce_negative_net_pay.
    """
    line_components: List[LineItemComponent] = []

    prorated_basic = _prorate(data.basic_pay, data.days_present, data.total_working_days)
    line_components.append(LineItemComponent("earning", "Basic Pay", prorated_basic))

    if data.hra:
        line_components.append(
            LineItemComponent("earning", "HRA", _prorate(data.hra, data.days_present, data.total_working_days))
        )

    if data.conveyance_allowance:
        line_components.append(
            LineItemComponent(
                "earning",
                "Conveyance Allowance",
                _prorate(data.conveyance_allowance, data.days_present, data.total_working_days),
            )
        )

    total_deductions = Decimal("0.00")
    for component in data.components:
        if component.component_type == "allowance":
            prorated = _prorate(component.amount, data.days_present, data.total_working_days)
            line_components.append(LineItemComponent("earning", component.name, prorated))
        elif component.component_type == "deduction":
            amount = _round(component.amount)
            line_components.append(LineItemComponent("deduction", component.name, amount))
            total_deductions += amount
        # Any other component_type is ignored defensively -- validated at the
        # form layer already, but the engine doesn't trust callers blindly.

    gross_pay = sum((c.amount for c in line_components if c.component_type == "earning"), Decimal("0.00"))
    net_pay = gross_pay - total_deductions

    return PayrollResult(
        employee_id=data.employee_id,
        employee_code=data.employee_code,
        employee_name=data.employee_name,
        days_present=data.days_present,
        days_on_leave=data.days_on_leave,
        gross_pay=gross_pay,
        total_deductions=total_deductions,
        net_pay=net_pay,
        line_components=line_components,
    )


def calculate_payroll_run(inputs: List[PayrollInput]) -> PayrollRunResult:
    """Runs calculate_payroll_for_employee() for every input and aggregates the totals."""
    line_items = [calculate_payroll_for_employee(data) for data in inputs]
    return PayrollRunResult(
        line_items=line_items,
        total_gross=sum((li.gross_pay for li in line_items), Decimal("0.00")),
        total_deductions=sum((li.total_deductions for li in line_items), Decimal("0.00")),
        total_net_pay=sum((li.net_pay for li in line_items), Decimal("0.00")),
        employee_count=len(line_items),
    )
