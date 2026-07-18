"""
Tests for Phase 14 Analytics and Enhanced Reporting Dashboard.
"""
from datetime import date
from decimal import Decimal
import pytest

from app.dependencies import SessionLocal
from app.models import Employee, PayrollLineItem, PayrollRun, User
from app.services.dashboard_service import (
    get_payroll_trend,
    get_compensation_breakdown,
    get_headcount_trend,
)
from tests.conftest import extract_csrf_token
from tests.test_rbac import _seed_user, _login


def test_analytics_dashboard_service(client):
    db = SessionLocal()
    try:
        # Seed user for run_by_user_id foreign key
        user = User(username="analytics_test_user", password_hash="hash", role="admin")
        db.add(user)
        db.flush()

        # Seed employee
        emp = Employee(
            employee_code="EMP_ANALYTICS",
            full_name="Analytics Tester",
            designation="Analyst",
            joining_date=date(2024, 1, 1),
            status="active",
        )
        db.add(emp)
        db.flush()

        # Seed multiple payroll runs to check trend logic
        run1 = PayrollRun(
            id=201,
            period=date(2024, 1, 1),
            status="completed",
            total_gross=Decimal("100000.00"),
            total_deductions=Decimal("10000.00"),
            total_net_pay=Decimal("90000.00"),
            employee_count=1,
            run_by_user_id=user.id,
        )
        run2 = PayrollRun(
            id=202,
            period=date(2024, 2, 1),
            status="completed",
            total_gross=Decimal("120000.00"),
            total_deductions=Decimal("12000.00"),
            total_net_pay=Decimal("108000.00"),
            employee_count=1,
            run_by_user_id=user.id,
        )
        db.add_all([run1, run2])
        db.flush()

        # Seed PayrollLineItem with components for run2
        item = PayrollLineItem(
            payroll_run_id=202,
            employee_id=emp.id,
            employee_code_snapshot="EMP_ANALYTICS",
            employee_name_snapshot="Analytics Tester",
            days_present_snapshot=Decimal("20.00"),
            days_on_leave_snapshot=Decimal("0.00"),
            gross_pay=Decimal("120000.00"),
            total_deductions=Decimal("12000.00"),
            net_pay=Decimal("108000.00"),
        )
        db.add(item)
        db.flush()

        # Import model to seed line item components
        from app.models.payroll import PayrollLineItemComponent
        c1 = PayrollLineItemComponent(
            payroll_line_item_id=item.id,
            name="Basic Salary",
            amount=Decimal("80000.00"),
            component_type="earning",
        )
        c2 = PayrollLineItemComponent(
            payroll_line_item_id=item.id,
            name="HRA",
            amount=Decimal("40000.00"),
            component_type="earning",
        )
        c3 = PayrollLineItemComponent(
            payroll_line_item_id=item.id,
            name="Provident Fund (PF)",
            amount=Decimal("12000.00"),
            component_type="deduction",
        )
        db.add_all([c1, c2, c3])
        db.commit()

        # Test dashboard helper services
        trends = get_payroll_trend(db)
        assert len(trends) == 2
        assert trends[0]["total_gross"] == 100000.0
        assert trends[1]["total_gross"] == 120000.0
        assert trends[0]["period"] == "January 2024"
        assert trends[1]["period"] == "February 2024"

        headcount = get_headcount_trend(db)
        assert len(headcount) == 2
        assert headcount[0]["employee_count"] == 1

        breakdown = get_compensation_breakdown(db)
        assert breakdown["period"] == "February 2024"
        assert "Basic Salary" in breakdown["categories"]
        assert "HRA" in breakdown["categories"]
        assert "Provident Fund (PF)" in breakdown["categories"]
        assert 80000.0 in breakdown["values"]

    finally:
        db.close()


def test_analytics_rbac_and_endpoints(client):
    # 1. Seed users
    admin_user, admin_pass = _seed_user("admin", "analytics_admin")
    mgr_user, mgr_pass = _seed_user("manager", "analytics_mgr")
    emp_user, emp_pass = _seed_user("employee", "analytics_emp")

    # 2. Test Admin access
    _login(client, admin_user, admin_pass)
    resp = client.get("/analytics")
    assert resp.status_code == 200
    assert "Analytics" in resp.text

    resp_api = client.get("/analytics/data/payroll-trend")
    assert resp_api.status_code == 200
    assert isinstance(resp_api.json(), list)

    # 3. Test Manager access
    _login(client, mgr_user, mgr_pass)
    resp = client.get("/analytics")
    assert resp.status_code == 200

    # 4. Test Employee access - must be denied (403)
    _login(client, emp_user, emp_pass)
    resp = client.get("/analytics")
    assert resp.status_code == 403

    resp_api = client.get("/analytics/data/payroll-trend")
    assert resp_api.status_code == 403
