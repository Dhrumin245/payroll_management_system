"""
Phase 4c checks: the payroll calculation engine. This is the highest-stakes
module in the app (Implementation Plan's own risk callout) -- these tests
run with zero dependencies beyond the standard library's decimal module,
deliberately, so they can be trusted independent of the database or web
framework working correctly. Run with: pytest
"""
from decimal import Decimal

from app.services.payroll_engine import (
    PayrollInput,
    SalaryComponentInput,
    calculate_payroll_for_employee,
    calculate_payroll_run,
)


def _input(**overrides) -> PayrollInput:
    defaults = dict(
        employee_id=1,
        employee_code="EMP0001",
        employee_name="Test Employee",
        basic_pay=Decimal("30000"),
        hra=Decimal("0"),
        conveyance_allowance=Decimal("0"),
        components=[],
        days_present=Decimal("27"),
        days_on_leave=Decimal("0"),
        total_working_days=Decimal("27"),
    )
    defaults.update(overrides)
    return PayrollInput(**defaults)


def test_full_attendance_no_optional_components():
    result = calculate_payroll_for_employee(_input())
    assert result.gross_pay == Decimal("30000.00")
    assert result.total_deductions == Decimal("0.00")
    assert result.net_pay == Decimal("30000.00")
    assert len(result.line_components) == 1  # only Basic Pay -- HRA/conveyance skipped when zero


def test_full_attendance_with_multiple_allowances_and_deductions():
    result = calculate_payroll_for_employee(
        _input(
            basic_pay=Decimal("60000"),
            hra=Decimal("24000"),
            conveyance_allowance=Decimal("2000"),
            components=[
                SalaryComponentInput("allowance", "Special Allowance", Decimal("3000")),
                SalaryComponentInput("deduction", "Provident Fund", Decimal("7200")),
                SalaryComponentInput("deduction", "Professional Tax", Decimal("200")),
            ],
        )
    )
    assert result.gross_pay == Decimal("89000.00")  # 60000 + 24000 + 2000 + 3000
    assert result.total_deductions == Decimal("7400.00")  # 7200 + 200
    assert result.net_pay == Decimal("81600.00")
    assert len(result.line_components) == 6


def test_partial_attendance_prorates_earnings_but_not_deductions():
    result = calculate_payroll_for_employee(
        _input(
            basic_pay=Decimal("50000"),
            hra=Decimal("20000"),
            components=[SalaryComponentInput("deduction", "Professional Tax", Decimal("200"))],
            days_present=Decimal("15"),
            total_working_days=Decimal("27"),
        )
    )
    expected_basic = (Decimal("50000") * Decimal("15") / Decimal("27")).quantize(Decimal("0.01"))
    expected_hra = (Decimal("20000") * Decimal("15") / Decimal("27")).quantize(Decimal("0.01"))
    assert result.gross_pay == expected_basic + expected_hra
    assert result.total_deductions == Decimal("200.00")  # unprorated, per the engine's documented decision
    assert result.net_pay == result.gross_pay - Decimal("200.00")


def test_zero_attendance_can_produce_negative_net_pay():
    """
    Deliberate behavior, not a bug: an active employee with zero attendance
    for the whole period has zero gross pay, but fixed deductions still
    apply in full -- net pay is honestly negative rather than floored at
    zero, per payroll_engine.py's documented decision.
    """
    result = calculate_payroll_for_employee(
        _input(
            basic_pay=Decimal("40000"),
            components=[SalaryComponentInput("deduction", "Professional Tax", Decimal("200"))],
            days_present=Decimal("0"),
            days_on_leave=Decimal("27"),
        )
    )
    assert result.gross_pay == Decimal("0.00")
    assert result.total_deductions == Decimal("200.00")
    assert result.net_pay == Decimal("-200.00")


def test_proration_rounds_half_up_on_non_terminating_division():
    # 50000 * 10 / 3 = 166666.666... -> rounds to 166666.67
    result = calculate_payroll_for_employee(
        _input(basic_pay=Decimal("50000"), days_present=Decimal("10"), total_working_days=Decimal("3"))
    )
    assert result.gross_pay == Decimal("166666.67")


def test_zero_total_working_days_does_not_divide_by_zero():
    """Defensive: a malformed/edge-case period shouldn't crash the engine."""
    result = calculate_payroll_for_employee(_input(days_present=Decimal("0"), total_working_days=Decimal("0")))
    assert result.gross_pay == Decimal("0.00")


def test_run_aggregates_totals_across_employees():
    inputs = [
        _input(employee_id=1, employee_code="EMP0001", basic_pay=Decimal("30000")),
        _input(
            employee_id=2,
            employee_code="EMP0002",
            basic_pay=Decimal("50000"),
            hra=Decimal("20000"),
            components=[SalaryComponentInput("deduction", "PF", Decimal("6000"))],
        ),
    ]
    run_result = calculate_payroll_run(inputs)
    assert run_result.employee_count == 2
    assert run_result.total_gross == Decimal("30000.00") + Decimal("70000.00")
    assert run_result.total_deductions == Decimal("6000.00")
    assert run_result.total_net_pay == run_result.total_gross - run_result.total_deductions
