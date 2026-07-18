"""
Statutory Compliance Service — Phase 12.

Pure computation functions for:
  - Provident Fund (PF)   : 12% of basic, capped at ₹1,800/month
  - Employee State Insurance (ESI) : 0.75% of gross, only when gross ≤ ₹21,000
  - Professional Tax (PT) : slab-based, state-specific

Plus config accessor helpers for the settings UI.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.statutory import PtSlab, StatutoryConfig
from app.services.payroll_engine import SalaryComponentInput

# ── Constants ──────────────────────────────────────────────────────────────

PF_RATE = Decimal("0.12")
PF_CAP = Decimal("1800.00")

ESI_RATE = Decimal("0.0075")
ESI_GROSS_CEILING = Decimal("21000.00")

_TWO = Decimal("0.01")

# Indian state codes that have PT
PT_STATES = {
    "MH": "Maharashtra",
    "KA": "Karnataka",
    "WB": "West Bengal",
    "TN": "Tamil Nadu",
    "AP": "Andhra Pradesh",
    "TG": "Telangana",
    "GJ": "Gujarat",
    "MP": "Madhya Pradesh",
    "KL": "Kerala",
}


# ── Config helpers ─────────────────────────────────────────────────────────

def get_config(db: Session, key: str) -> Optional[str]:
    """Return the string value for a config key, or None if missing."""
    row = db.query(StatutoryConfig).filter(StatutoryConfig.key == key).first()
    return row.value if row else None


def get_all_configs(db: Session) -> Dict[str, str]:
    """Return all config rows as a {key: value} dict."""
    rows = db.query(StatutoryConfig).all()
    return {r.key: r.value for r in rows}


def set_config(db: Session, key: str, value: str, user_id: Optional[int] = None) -> None:
    """Upsert a config row."""
    row = db.query(StatutoryConfig).filter(StatutoryConfig.key == key).first()
    if row:
        row.value = value
        row.updated_by_user_id = user_id
    else:
        db.add(StatutoryConfig(key=key, value=value, updated_by_user_id=user_id))


def _is_enabled(db: Session, key: str) -> bool:
    val = get_config(db, key)
    return val is not None and val.lower() in ("true", "1", "yes")


# ── PF ─────────────────────────────────────────────────────────────────────

def compute_pf(basic_pay: Decimal) -> Decimal:
    """
    PF = 12% of basic_pay, capped at ₹1,800/month.
    Always rounded to 2 decimals (half-up).
    """
    raw = (basic_pay * PF_RATE).quantize(_TWO, rounding=ROUND_HALF_UP)
    return min(raw, PF_CAP)


# ── ESI ────────────────────────────────────────────────────────────────────

def compute_esi(gross_pay: Decimal) -> Decimal:
    """
    ESI = 0.75% of gross_pay, but only when gross ≤ ₹21,000.
    Returns Decimal("0.00") if gross exceeds the ceiling.
    """
    if gross_pay > ESI_GROSS_CEILING:
        return Decimal("0.00")
    return (gross_pay * ESI_RATE).quantize(_TWO, rounding=ROUND_HALF_UP)


# ── Professional Tax ──────────────────────────────────────────────────────

def compute_pt(gross_pay: Decimal, state_code: str, db: Session) -> Decimal:
    """
    Look up the PT slab matching (state_code, gross_pay) and return the
    monthly_tax amount. Returns 0 if no slab matches.
    """
    slabs = (
        db.query(PtSlab)
        .filter(PtSlab.state_code == state_code)
        .order_by(PtSlab.gross_from)
        .all()
    )
    for slab in slabs:
        if gross_pay >= slab.gross_from:
            if slab.gross_to is None or gross_pay <= slab.gross_to:
                return slab.monthly_tax
    return Decimal("0.00")


def get_pt_slabs(db: Session, state_code: str) -> List[PtSlab]:
    """Return all PT slabs for a state, ordered by gross_from."""
    return (
        db.query(PtSlab)
        .filter(PtSlab.state_code == state_code)
        .order_by(PtSlab.gross_from)
        .all()
    )


def get_all_pt_slabs(db: Session) -> List[PtSlab]:
    """Return all PT slabs across all states."""
    return db.query(PtSlab).order_by(PtSlab.state_code, PtSlab.gross_from).all()


# ── Composite helper for payroll integration ──────────────────────────────

def get_statutory_deductions(
    db: Session,
    basic_pay: Decimal,
    gross_pay: Decimal,
    existing_component_names: set,
) -> List[SalaryComponentInput]:
    """
    Compute all enabled statutory deductions and return them as
    SalaryComponentInput items ready for the payroll engine.

    If the employee already has a manual deduction with the same name
    (e.g. "Provident Fund"), the auto-computed version is skipped —
    this allows per-employee overrides.
    """
    deductions: List[SalaryComponentInput] = []

    # Provident Fund
    if _is_enabled(db, "pf_enabled"):
        pf_name = "Provident Fund (PF)"
        if pf_name not in existing_component_names:
            pf_amount = compute_pf(basic_pay)
            if pf_amount > 0:
                deductions.append(
                    SalaryComponentInput(
                        component_type="deduction",
                        name=pf_name,
                        amount=pf_amount,
                    )
                )

    # Employee State Insurance
    if _is_enabled(db, "esi_enabled"):
        esi_name = "Employee State Insurance (ESI)"
        if esi_name not in existing_component_names:
            esi_amount = compute_esi(gross_pay)
            if esi_amount > 0:
                deductions.append(
                    SalaryComponentInput(
                        component_type="deduction",
                        name=esi_name,
                        amount=esi_amount,
                    )
                )

    # Professional Tax
    if _is_enabled(db, "pt_enabled"):
        pt_name = "Professional Tax (PT)"
        if pt_name not in existing_component_names:
            state_code = get_config(db, "pt_state") or "MH"
            pt_amount = compute_pt(gross_pay, state_code, db)
            if pt_amount > 0:
                deductions.append(
                    SalaryComponentInput(
                        component_type="deduction",
                        name=pt_name,
                        amount=pt_amount,
                    )
                )

    return deductions
