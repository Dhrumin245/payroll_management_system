"""
Tests for Phase 12: Tax & Statutory Compliance (PF, ESI, PT).
"""
from decimal import Decimal
from datetime import date
import pytest

from app.dependencies import SessionLocal
from app.models import Employee, SalaryStructure, AttendanceRecord, PtSlab, StatutoryConfig, User
from app.services.security import hash_password
from app.services.statutory_service import (
    compute_pf,
    compute_esi,
    compute_pt,
    get_statutory_deductions,
    set_config,
)
from app.services.payroll_service import run_payroll


def _seed_statutory_data(db):
    # Set default configs
    db.add(StatutoryConfig(key="pf_enabled", value="false"))
    db.add(StatutoryConfig(key="esi_enabled", value="false"))
    db.add(StatutoryConfig(key="pt_enabled", value="false"))
    db.add(StatutoryConfig(key="pt_state", value="MH"))

    # Seed PT slabs
    # MH:
    # 0 - 7500: 0
    # 7501 - 10000: 175
    # 10001+: 200
    db.add(PtSlab(state_code="MH", gross_from=Decimal("0.00"), gross_to=Decimal("7500.00"), monthly_tax=Decimal("0.00")))
    db.add(PtSlab(state_code="MH", gross_from=Decimal("7501.00"), gross_to=Decimal("10000.00"), monthly_tax=Decimal("175.00")))
    db.add(PtSlab(state_code="MH", gross_from=Decimal("10001.00"), gross_to=None, monthly_tax=Decimal("200.00")))

    # KA:
    # 0 - 15000: 0
    # 15001+: 200
    db.add(PtSlab(state_code="KA", gross_from=Decimal("0.00"), gross_to=Decimal("15000.00"), monthly_tax=Decimal("0.00")))
    db.add(PtSlab(state_code="KA", gross_from=Decimal("15001.00"), gross_to=None, monthly_tax=Decimal("200.00")))

    # Seed User with ID=1 if not exists
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        db.add(User(id=1, username="testadmin_1", password_hash=hash_password("testpass123"), role="admin"))

    db.commit()


def test_compute_pf():
    # 12% of 10000 = 1200
    assert compute_pf(Decimal("10000.00")) == Decimal("1200.00")
    # 12% of 15000 = 1800 (exact cap)
    assert compute_pf(Decimal("15000.00")) == Decimal("1800.00")
    # 12% of 20000 = 2400 capped at 1800
    assert compute_pf(Decimal("20000.00")) == Decimal("1800.00")
    # Small decimal rounding: 12% of 10000.45 = 1200.054 -> 1200.05
    assert compute_pf(Decimal("10000.45")) == Decimal("1200.05")
    # Small decimal rounding: 12% of 10000.46 = 1200.0552 -> 1200.06
    assert compute_pf(Decimal("10000.46")) == Decimal("1200.06")


def test_compute_esi():
    # 0.75% of 15000 = 112.50
    assert compute_esi(Decimal("15000.00")) == Decimal("112.50")
    # 0.75% of 21000 = 157.50
    assert compute_esi(Decimal("21000.00")) == Decimal("157.50")
    # Above 21000 = 0.00
    assert compute_esi(Decimal("21000.01")) == Decimal("0.00")
    assert compute_esi(Decimal("30000.00")) == Decimal("0.00")


def test_compute_pt(client):
    db = SessionLocal()
    _seed_statutory_data(db)

    # MH slabs (from seeds):
    # 0 - 7500: 0
    # 7501 - 10000: 175
    # 10001+: 200
    assert compute_pt(Decimal("5000.00"), "MH", db) == Decimal("0.00")
    assert compute_pt(Decimal("7500.00"), "MH", db) == Decimal("0.00")
    assert compute_pt(Decimal("7501.00"), "MH", db) == Decimal("175.00")
    assert compute_pt(Decimal("9000.00"), "MH", db) == Decimal("175.00")
    assert compute_pt(Decimal("10000.00"), "MH", db) == Decimal("175.00")
    assert compute_pt(Decimal("10001.00"), "MH", db) == Decimal("200.00")
    assert compute_pt(Decimal("25000.00"), "MH", db) == Decimal("200.00")

    # KA slabs (from seeds):
    # 0 - 15000: 0
    # 15001+: 200
    assert compute_pt(Decimal("12000.00"), "KA", db) == Decimal("0.00")
    assert compute_pt(Decimal("15000.00"), "KA", db) == Decimal("0.00")
    assert compute_pt(Decimal("15001.00"), "KA", db) == Decimal("200.00")
    db.close()


def test_get_statutory_deductions(client):
    db = SessionLocal()
    _seed_statutory_data(db)

    # By default, configs are false. No deductions should be returned.
    deductions = get_statutory_deductions(db, Decimal("10000.00"), Decimal("15000.00"), set())
    assert len(deductions) == 0

    # Enable PF and ESI
    set_config(db, "pf_enabled", "true")
    set_config(db, "esi_enabled", "true")
    db.commit()

    deductions = get_statutory_deductions(db, Decimal("10000.00"), Decimal("15000.00"), set())
    assert len(deductions) == 2
    pf = next(d for d in deductions if "PF" in d.name)
    esi = next(d for d in deductions if "ESI" in d.name)
    assert pf.amount == Decimal("1200.00")
    assert esi.amount == Decimal("112.50")

    # Override: if PF already in existing names, auto-computed PF should be skipped.
    deductions_overridden = get_statutory_deductions(
        db, Decimal("10000.00"), Decimal("15000.00"), {"Provident Fund (PF)"}
    )
    assert len(deductions_overridden) == 1
    assert "ESI" in deductions_overridden[0].name
    db.close()


def test_settings_routes(logged_in_client):
    client, csrf_token = logged_in_client
    db = SessionLocal()
    _seed_statutory_data(db)

    # GET /settings
    res = client.get("/settings")
    assert res.status_code == 200
    assert "Statutory Settings" in res.text

    # POST /settings/statutory
    res = client.post(
        "/settings/statutory",
        data={
            "pf_enabled": "true",
            "esi_enabled": "false",
            "pt_enabled": "true",
            "pt_state": "MH",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/settings"

    # Verify database state after POST
    configs = {c.key: c.value for c in db.query(StatutoryConfig).all()}
    assert configs.get("pf_enabled") == "true"
    assert configs.get("esi_enabled") == "false"
    assert configs.get("pt_enabled") == "true"
    assert configs.get("pt_state") == "MH"

    # GET /settings/pt-slabs
    res = client.get("/settings/pt-slabs?state=MH")
    assert res.status_code == 200
    assert "Professional Tax Slabs" in res.text
    assert "7,501.00" in res.text

    # POST /settings/pt-slabs/save - add a new slab for MH
    res = client.post(
        "/settings/pt-slabs/save",
        data={
            "state_code": "MH",
            "slab_id": "",
            "gross_from": "50000.00",
            "gross_to": "60000.00",
            "monthly_tax": "300.00",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/settings/pt-slabs?state=MH"

    # Verify newly added slab
    slab = db.query(PtSlab).filter(PtSlab.state_code == "MH", PtSlab.gross_from == 50000).first()
    assert slab is not None
    assert slab.gross_to == Decimal("60000.00")
    assert slab.monthly_tax == Decimal("300.00")

    # POST /settings/pt-slabs/save - edit the newly added slab
    res = client.post(
        "/settings/pt-slabs/save",
        data={
            "state_code": "MH",
            "slab_id": str(slab.id),
            "gross_from": "50000.00",
            "gross_to": "",  # change to infinity
            "monthly_tax": "350.00",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    db.refresh(slab)
    assert slab.gross_to is None
    assert slab.monthly_tax == Decimal("350.00")

    # POST /settings/pt-slabs/delete/{slab_id}
    res = client.post(
        f"/settings/pt-slabs/delete/{slab.id}",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert db.query(PtSlab).filter(PtSlab.id == slab.id).first() is None
    db.close()


def test_payroll_run_injects_statutory_deductions(client):
    db = SessionLocal()
    _seed_statutory_data(db)

    # 1. Enable statutory deductions
    set_config(db, "pf_enabled", "true")
    set_config(db, "esi_enabled", "true")
    set_config(db, "pt_enabled", "true")
    set_config(db, "pt_state", "MH")
    db.commit()

    # 2. Seed an employee with a salary structure
    emp = Employee(
        employee_code="EMP9999",
        full_name="Statutory Employee",
        designation="Developer",
        joining_date=date(2024, 1, 1),
        status="active",
    )
    db.add(emp)
    db.flush()

    # Monthly salary structure:
    # basic: 10000 (PF should be 12% of 10000 = 1200)
    # hra: 4000
    # conveyance: 1000
    # Total fixed monthly: 15000
    struct = SalaryStructure(
        employee_id=emp.id,
        basic_pay=Decimal("10000.00"),
        hra=Decimal("4000.00"),
        conveyance_allowance=Decimal("1000.00"),
        effective_from=date(2024, 1, 1),
    )
    db.add(struct)

    # 3. Add attendance record (100% attendance, so earned gross is exactly 15000)
    # Since gross is 15000:
    # ESI = 0.75% of 15000 = 112.50
    # PT for MH (gross 15000) = 200.00
    attendance = AttendanceRecord(
        employee_id=emp.id,
        period=date(2024, 1, 1),
        days_present=Decimal("20.00"),
        days_on_leave=Decimal("0.00"),
        total_working_days=Decimal("20.00"),
    )
    db.add(attendance)
    db.commit()

    # 4. Run payroll (user_id=1 exists due to _seed_statutory_data)
    run_payroll(db, date(2024, 1, 1), run_by_user_id=1)

    # 5. Fetch line item and components
    db.commit()
    from app.models import PayrollLineItem
    line_item = (
        db.query(PayrollLineItem)
        .filter(PayrollLineItem.employee_id == emp.id)
        .first()
    )
    assert line_item is not None
    assert line_item.gross_pay == Decimal("15000.00")

    # Assert components were created
    comps = {c.name: c.amount for c in line_item.components}
    assert comps.get("Provident Fund (PF)") == Decimal("1200.00")
    assert comps.get("Employee State Insurance (ESI)") == Decimal("112.50")
    assert comps.get("Professional Tax (PT)") == Decimal("200.00")

    # Deductions total: 1200 + 112.50 + 200 = 1512.50
    assert line_item.total_deductions == Decimal("1512.50")
    assert line_item.net_pay == Decimal("13487.50")

    db.close()
