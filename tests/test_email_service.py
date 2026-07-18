"""
Tests for Phase 13 email service.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services.email_service import send_payslip_email


@pytest.mark.anyio
async def test_email_disabled_skips_dispatch(caplog):
    # Set email disabled
    with patch.object(settings, "EMAIL_ENABLED", False):
        await send_payslip_email(
            employee_email="test@employee.com",
            employee_name="Test Employee",
            period_label="January 2024",
            pdf_bytes=b"fake-pdf-content",
        )
    # Verify warning logged
    assert "Email dispatch is disabled" in caplog.text


@pytest.mark.anyio
async def test_email_missing_address_skips_dispatch(caplog):
    # Set email enabled
    with patch.object(settings, "EMAIL_ENABLED", True):
        await send_payslip_email(
            employee_email="",
            employee_name="Test Employee",
            period_label="January 2024",
            pdf_bytes=b"fake-pdf-content",
        )
    # Verify warning logged
    assert "No email address configured" in caplog.text


@pytest.mark.anyio
@patch("aiosmtplib.SMTP")
async def test_email_enabled_sends_successfully(mock_smtp_class):
    # Setup mock SMTP instance
    mock_smtp = AsyncMock()
    mock_smtp_class.return_value.__aenter__.return_value = mock_smtp

    with patch.object(settings, "EMAIL_ENABLED", True), \
         patch.object(settings, "SMTP_HOST", "smtp.test.com"), \
         patch.object(settings, "SMTP_PORT", 587), \
         patch.object(settings, "SMTP_USER", "user@test.com"), \
         patch.object(settings, "SMTP_PASSWORD", "password123"), \
         patch.object(settings, "EMAIL_FROM", "payout@test.com"):
         
        await send_payslip_email(
            employee_email="emp@test.com",
            employee_name="John Doe",
            period_label="January 2024",
            pdf_bytes=b"pdf-data-stream",
        )

    # Verify SMTP initialization args
    mock_smtp_class.assert_called_once_with(
        hostname="smtp.test.com",
        port=587,
        use_tls=False,
        start_tls=True,
    )

    # Verify SMTP login and send message calls
    mock_smtp.login.assert_called_once_with("user@test.com", "password123")
    mock_smtp.send_message.assert_called_once()
    
    # Inspect the sent message
    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert sent_msg["Subject"] == "Payslip for January 2024 — Your Company Name"
    assert sent_msg["To"] == "emp@test.com"
    assert sent_msg["From"] == "payout@test.com"
    
    # Assert attachment is present
    attachments = list(sent_msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "payslip_January_2024.pdf"
    assert attachments[0].get_content() == b"pdf-data-stream"
