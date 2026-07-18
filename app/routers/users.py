"""
User Management Router — admin-only pages for creating and managing
login accounts (admin, manager, employee roles).
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_admin
from app.flash import flash
from app.models import Employee, User
from app.services.csrf import verify_csrf
from app.services.security import hash_password
from app.templating import render

router = APIRouter()


@router.get("/users")
def list_users(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all user accounts."""
    users = db.query(User).order_by(User.created_at.desc()).all()

    # Pre-fetch linked employee names for display
    employee_map = {}
    linked_ids = [u.employee_id for u in users if u.employee_id]
    if linked_ids:
        employees = db.query(Employee).filter(Employee.id.in_(linked_ids)).all()
        employee_map = {e.id: e for e in employees}

    return render(
        request,
        "users/list.html",
        {
            "user": user,
            "active_nav": "users",
            "all_users": users,
            "employee_map": employee_map,
        },
    )


@router.get("/users/new")
def new_user_form(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Show the create-user form."""
    # Fetch active employees that are NOT yet linked to any user account
    linked_employee_ids = (
        db.query(User.employee_id)
        .filter(User.employee_id.isnot(None))
        .all()
    )
    linked_ids = {row[0] for row in linked_employee_ids}

    available_employees = (
        db.query(Employee)
        .filter(Employee.status == "active")
        .order_by(Employee.employee_code)
        .all()
    )
    available_employees = [e for e in available_employees if e.id not in linked_ids]

    return render(
        request,
        "users/new.html",
        {
            "user": user,
            "active_nav": "users",
            "available_employees": available_employees,
            "form_values": {},
            "form_errors": {},
        },
    )


@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    role: str = Form(...),
    employee_id: str = Form(""),
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Handle new user creation form submission."""
    verify_csrf(request, csrf_token)

    errors: dict[str, str] = {}
    form_values = {
        "username": username,
        "role": role,
        "employee_id": employee_id,
    }

    # Validation
    username = username.strip()
    if not username:
        errors["username"] = "Username is required."
    elif len(username) < 3:
        errors["username"] = "Username must be at least 3 characters."
    elif db.query(User).filter(User.username == username).first():
        errors["username"] = f"Username '{username}' is already taken."

    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    elif password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if role not in ("admin", "manager", "employee"):
        errors["role"] = "Invalid role selected."

    emp_id_value = None
    if role == "employee":
        if not employee_id:
            errors["employee_id"] = "An employee record must be selected for the 'employee' role."
        else:
            try:
                emp_id_value = int(employee_id)
            except ValueError:
                errors["employee_id"] = "Invalid employee selection."
            else:
                emp = db.query(Employee).filter(Employee.id == emp_id_value).first()
                if not emp:
                    errors["employee_id"] = "Selected employee not found."
                # Check if already linked
                existing_link = (
                    db.query(User)
                    .filter(User.employee_id == emp_id_value)
                    .first()
                )
                if existing_link:
                    errors["employee_id"] = f"This employee is already linked to user '{existing_link.username}'."

    if errors:
        # Re-render form with errors
        linked_employee_ids = (
            db.query(User.employee_id)
            .filter(User.employee_id.isnot(None))
            .all()
        )
        linked_ids = {row[0] for row in linked_employee_ids}
        available_employees = (
            db.query(Employee)
            .filter(Employee.status == "active")
            .order_by(Employee.employee_code)
            .all()
        )
        available_employees = [e for e in available_employees if e.id not in linked_ids]

        return render(
            request,
            "users/new.html",
            {
                "user": user,
                "active_nav": "users",
                "available_employees": available_employees,
                "form_values": form_values,
                "form_errors": errors,
            },
        )

    # Create the user
    new_user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        employee_id=emp_id_value,
    )
    db.add(new_user)
    db.commit()

    flash(request, f"User '{username}' ({role}) created successfully.", "success")
    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reset another user's password."""
    verify_csrf(request, csrf_token)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)

    if not new_password or len(new_password) < 6:
        flash(request, "Password must be at least 6 characters.", "error")
        return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)

    if new_password != confirm_new_password:
        flash(request, "Passwords do not match.", "error")
        return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)

    target_user.password_hash = hash_password(new_password)
    db.commit()

    flash(request, f"Password for '{target_user.username}' has been reset.", "success")
    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Activate or deactivate a user account."""
    verify_csrf(request, csrf_token)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)

    # Prevent admin from deactivating themselves
    if target_user.id == user.id:
        flash(request, "You cannot deactivate your own account.", "error")
        return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)

    target_user.is_active = not target_user.is_active
    action = "activated" if target_user.is_active else "deactivated"
    db.commit()

    flash(request, f"User '{target_user.username}' has been {action}.", "success")
    return RedirectResponse(url="/users", status_code=status.HTTP_303_SEE_OTHER)
