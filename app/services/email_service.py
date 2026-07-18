"""
Email Service — Phase 13.

Sends payslip PDF documents as email attachments using async SMTP dispatch.
"""
from email.message import EmailMessage
import logging
import aiosmtplib

from app.config import settings
from app.templating import templates

logger = logging.getLogger("app")


async def send_payslip_email(
    employee_email: str,
    employee_name: str,
    period_label: str,
    pdf_bytes: bytes,
) -> None:
    """
    Builds and sends a multipart email to the employee with their payslip PDF.
    If EMAIL_ENABLED is False, skips sending but logs a warning.
    """
    if not settings.EMAIL_ENABLED:
        logger.warning(
            "Email dispatch is disabled (EMAIL_ENABLED=False). "
            "Skipping payslip email to %s (%s).",
            employee_name,
            employee_email,
        )
        return

    if not employee_email:
        logger.warning(
            "No email address configured for %s. Skipping payslip email.",
            employee_name,
        )
        return

    logger.info(
        "Preparing to send payslip email to %s (%s) for %s.",
        employee_name,
        employee_email,
        period_label,
    )

    # Render HTML message body
    try:
        template = templates.get_template("email/payslip.html")
        html_body = template.render(
            employee_name=employee_name,
            period_label=period_label,
            company_name=settings.COMPANY_NAME,
        )
    except Exception as e:
        logger.error(
            "Failed to render payslip email template: %s. Reverting to text.",
            str(e),
        )
        html_body = (
            f"Dear {employee_name},\n\n"
            f"Please find attached your payslip for the pay period {period_label}.\n\n"
            f"Regards,\n{settings.COMPANY_NAME}"
        )

    # Build the email message
    msg = EmailMessage()
    msg["Subject"] = f"Payslip for {period_label} — {settings.COMPANY_NAME}"
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = employee_email

    # Add HTML body (falls back to plain text if HTML not supported)
    msg.set_content(
        f"Dear {employee_name},\n\n"
        f"Please find attached your payslip for the pay period {period_label}.\n\n"
        f"Regards,\n{settings.COMPANY_NAME}"
    )
    msg.add_alternative(html_body, subtype="html")

    # Attach PDF
    filename = f"payslip_{period_label.replace(' ', '_')}.pdf"
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    # Send asynchronously via SMTP
    try:
        # Use STARTTLS if port is 587, use SSL if port is 465, else plain SMTP
        use_tls = settings.SMTP_PORT == 465
        start_tls = settings.SMTP_PORT == 587

        smtp_args = {
            "hostname": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "use_tls": use_tls,
            "start_tls": start_tls,
        }

        # Connect and send
        async with aiosmtplib.SMTP(**smtp_args) as smtp:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg)

        logger.info(
            "Successfully sent payslip email to %s (%s) for %s.",
            employee_name,
            employee_email,
            period_label,
        )
    except Exception as e:
        logger.error(
            "SMTP dispatch failed for %s (%s): %s",
            employee_name,
            employee_email,
            str(e),
            exc_info=True,
        )
        # We don't raise here, so other emails in the loop can continue to process
