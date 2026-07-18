"""
Settings Router — Phase 12.

Handles company-wide settings:
  - Enabling/disabling statutory deductions (PF, ESI, PT)
  - Selecting PT State
  - Managing PT Slabs (CRUD)
"""
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.flash import flash
from app.models import User, PtSlab
from app.services.csrf import verify_csrf
from app.services.statutory_service import (
    PT_STATES,
    get_all_configs,
    get_config,
    get_pt_slabs,
    set_config,
)
from app.templating import render

router = APIRouter()


@router.get("/settings")
def view_settings(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Render company-wide statutory settings."""
    configs = get_all_configs(db)

    # Defaults if missing
    pf_enabled = configs.get("pf_enabled", "false") == "true"
    esi_enabled = configs.get("esi_enabled", "false") == "true"
    pt_enabled = configs.get("pt_enabled", "false") == "true"
    pt_state = configs.get("pt_state", "MH")

    return render(
        request,
        "settings/index.html",
        {
            "user": user,
            "active_nav": "settings",
            "pf_enabled": pf_enabled,
            "esi_enabled": esi_enabled,
            "pt_enabled": pt_enabled,
            "pt_state": pt_state,
            "pt_states": PT_STATES,
        },
    )


@router.post("/settings/statutory")
def update_statutory_settings(
    request: Request,
    pf_enabled: str = Form("false"),
    esi_enabled: str = Form("false"),
    pt_enabled: str = Form("false"),
    pt_state: str = Form("MH"),
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save statutory config toggles."""
    verify_csrf(request, csrf_token)

    if pt_state not in PT_STATES:
        flash(request, "Invalid PT State selected.", "danger")
        return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)

    set_config(db, "pf_enabled", "true" if pf_enabled == "true" else "false", user.id)
    set_config(db, "esi_enabled", "true" if esi_enabled == "true" else "false", user.id)
    set_config(db, "pt_enabled", "true" if pt_enabled == "true" else "false", user.id)
    set_config(db, "pt_state", pt_state, user.id)

    db.commit()
    flash(request, "Statutory settings updated successfully.", "success")
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/settings/pt-slabs")
def view_pt_slabs(
    request: Request,
    state: str = "",
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """View PT slabs for a selected state."""
    if not state:
        state = get_config(db, "pt_state") or "MH"

    slabs = get_pt_slabs(db, state)

    return render(
        request,
        "settings/pt_slabs.html",
        {
            "user": user,
            "active_nav": "settings",
            "selected_state": state,
            "pt_states": PT_STATES,
            "slabs": slabs,
        },
    )


@router.post("/settings/pt-slabs/save")
def save_pt_slab(
    request: Request,
    state_code: str = Form(...),
    slab_id: str = Form(""),  # empty if creating
    gross_from: str = Form(...),
    gross_to: str = Form(""),  # empty for infinity
    monthly_tax: str = Form(...),
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create or update a Professional Tax slab."""
    verify_csrf(request, csrf_token)

    # Validations
    if state_code not in PT_STATES:
        flash(request, "Invalid State code.", "danger")
        return RedirectResponse(
            url=f"/settings/pt-slabs?state={state_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        g_from = Decimal(gross_from)
        m_tax = Decimal(monthly_tax)
        g_to = Decimal(gross_to) if gross_to.strip() else None
    except (InvalidOperation, ValueError):
        flash(request, "Gross bounds and Monthly Tax must be valid numeric values.", "danger")
        return RedirectResponse(
            url=f"/settings/pt-slabs?state={state_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if g_from < 0 or m_tax < 0:
        flash(request, "Values cannot be negative.", "danger")
        return RedirectResponse(
            url=f"/settings/pt-slabs?state={state_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if g_to is not None and g_to < g_from:
        flash(request, "Gross To cannot be less than Gross From.", "danger")
        return RedirectResponse(
            url=f"/settings/pt-slabs?state={state_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check overlaps/conflicts if we want, but simple CRUD is fine for now.
    if slab_id:
        slab = db.query(PtSlab).filter(PtSlab.id == int(slab_id)).first()
        if not slab:
            raise HTTPException(status_code=404, detail="Slab not found")
        slab.state_code = state_code
        slab.gross_from = g_from
        slab.gross_to = g_to
        slab.monthly_tax = m_tax
        flash(request, "Slab updated successfully.", "success")
    else:
        slab = PtSlab(
            state_code=state_code,
            gross_from=g_from,
            gross_to=g_to,
            monthly_tax=m_tax,
        )
        db.add(slab)
        flash(request, "Slab added successfully.", "success")

    db.commit()
    return RedirectResponse(
        url=f"/settings/pt-slabs?state={state_code}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/settings/pt-slabs/delete/{slab_id}")
def delete_pt_slab(
    request: Request,
    slab_id: int,
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a Professional Tax slab."""
    verify_csrf(request, csrf_token)

    slab = db.query(PtSlab).filter(PtSlab.id == slab_id).first()
    if not slab:
        raise HTTPException(status_code=404, detail="Slab not found")

    state_code = slab.state_code
    db.delete(slab)
    db.commit()

    flash(request, "Professional Tax slab deleted.", "success")
    return RedirectResponse(
        url=f"/settings/pt-slabs?state={state_code}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
