from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """
    Admin login accounts (Backend Schema §3.1).

    `employee_id` now has its ForeignKey constraint (added via migration
    0007, once `employees` exists) — Phase 1 deliberately left it as a bare
    column since `employees` didn't exist yet at that point.
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'employee')", name="ck_users_role"),)

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="admin")
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Phase 2 self-service, not used yet
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
