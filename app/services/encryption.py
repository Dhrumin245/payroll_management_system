"""
Field-level encryption for sensitive data — specifically bank account
numbers (Backend Schema §7). Uses Fernet (symmetric encryption) keyed by
BANK_ENCRYPTION_KEY, which is deliberately a separate secret from SECRET_KEY.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    if not settings.BANK_ENCRYPTION_KEY:
        raise RuntimeError(
            "BANK_ENCRYPTION_KEY is not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
            "and add it to .env."
        )
    return Fernet(settings.BANK_ENCRYPTION_KEY.encode())


def encrypt_account_number(account_number: str) -> str:
    """Returns ciphertext, suitable for storing in account_number_encrypted."""
    return _get_fernet().encrypt(account_number.encode()).decode()


def decrypt_account_number(ciphertext: str) -> str:
    """
    Returns the original plaintext account number. Never log or render this
    outside a deliberate need (e.g. a bank transfer export in Phase 5).
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Could not decrypt account number — invalid token or wrong key.") from exc


def last4_digits(account_number: str) -> str:
    """Returns the last 4 characters, for masked display (account_number_last4)."""
    return account_number[-4:]
