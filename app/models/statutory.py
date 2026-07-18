"""
Models for statutory compliance configuration (Phase 12).

StatutoryConfig — key-value store for company-wide toggles (PF/ESI/PT).
PtSlab          — Professional Tax slab lookup (state-specific).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StatutoryConfig(Base):
    """Company-wide key-value configuration for statutory compliance."""

    __tablename__ = "statutory_configs"

    id = Column(Integer, primary_key=True)
    key = Column(String(60), unique=True, nullable=False)
    value = Column(String(255), nullable=False, default="")
    updated_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    updated_by = relationship("User", foreign_keys=[updated_by_user_id])

    def __repr__(self) -> str:
        return f"<StatutoryConfig {self.key!r}={self.value!r}>"


class PtSlab(Base):
    """Professional Tax slab row for a specific Indian state."""

    __tablename__ = "pt_slabs"

    id = Column(Integer, primary_key=True)
    state_code = Column(String(10), nullable=False)
    gross_from = Column(Numeric(12, 2), nullable=False)
    gross_to = Column(Numeric(12, 2), nullable=True)  # NULL means no upper bound
    monthly_tax = Column(Numeric(8, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PtSlab {self.state_code} "
            f"{self.gross_from}–{self.gross_to or '∞'} → ₹{self.monthly_tax}>"
        )
