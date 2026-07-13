from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.services.encryption import decrypt_account_number, encrypt_account_number, last4_digits


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmployeeBankDetails(Base):
    """
    Bank details, kept in a separate table for tighter access/encryption
    control (Backend Schema §3.3). The raw account number is never stored or
    read directly -- `account_number` below is a Python property that
    transparently encrypts on write and decrypts on read (Backend Schema §7),
    keeping `account_number_last4` in sync automatically for masked display.
    """

    __tablename__ = "employee_bank_details"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False)
    account_holder_name = Column(String(120), nullable=False)
    account_number_encrypted = Column(Text, nullable=False)
    account_number_last4 = Column(String(4), nullable=False)
    ifsc_code = Column(String(20), nullable=True)
    bank_name = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    employee = relationship("Employee", back_populates="bank_details")

    @property
    def account_number(self) -> str:
        """Decrypts on read. Never log or render this outside a deliberate need."""
        return decrypt_account_number(self.account_number_encrypted)

    @account_number.setter
    def account_number(self, plaintext: str) -> None:
        """Encrypts on write; keeps account_number_last4 in sync automatically."""
        self.account_number_encrypted = encrypt_account_number(plaintext)
        self.account_number_last4 = last4_digits(plaintext)

    def __repr__(self) -> str:
        return f"<EmployeeBankDetails employee_id={self.employee_id} account=...{self.account_number_last4}>"
