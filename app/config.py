"""
Central application settings, loaded from environment variables (via .env locally,
real environment variables in production — never hardcoded, per the TRD/Backend
Schema security requirements).
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
    BANK_ENCRYPTION_KEY: str = os.environ.get("BANK_ENCRYPTION_KEY", "")
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    # Payslip letterhead (App Flow Screen 10 requires company details on
    # every payslip; there's no company_settings table -- this is static,
    # single-tenant config, per the planning docs' explicit decision).
    COMPANY_NAME: str = os.environ.get("COMPANY_NAME", "Your Company Name")
    COMPANY_ADDRESS: str = os.environ.get("COMPANY_ADDRESS", "")

    # Session cookie behavior (Backend Schema §6: 30-min idle / 8-hr absolute timeout).
    # The absolute cap is enforced here at the cookie level; the idle timeout is
    # checked against a last-activity timestamp stored in the session payload,
    # built out in Phase 1.
    SESSION_COOKIE_NAME: str = "payroll_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 8  # 8 hours

    # Operational integrations: Email / SMTP (Phase 13)
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER: str = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.environ.get("EMAIL_FROM", "")
    EMAIL_ENABLED: bool = os.environ.get("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")


settings = Settings()
