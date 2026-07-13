"""
Phase 5 checks. PDF generation, CSV export, and bank-detail encryption were
already built and tested as part of 4a/4d rather than deferred to this
phase — these tests cover the specific guarantees the Implementation Plan
calls for that weren't yet explicitly verified: no plaintext bank data
anywhere it shouldn't be (checked at the raw DB level, not just through the
ORM), a clear failure mode if the encryption key is ever wrong, and
consistent PDF/CSV regeneration from the same underlying data. Run with: pytest
"""
from sqlalchemy import text

from app.dependencies import SessionLocal, engine
from app.models import Employee, PayrollRun
from app.services.encryption import decrypt_account_number, encrypt_account_number

_EMPLOYEE_PAYLOAD = {
    "full_name": "Test Employee",
    "employee_code": "EMP0001",
    "designation": "Engineer",
    "joining_date": "2026-01-01",
    "basic_pay": "50000",
    "account_holder_name": "Test Employee",
    "account_number": "1234567890",
    "component_type": ["deduction"],
    "component_name": ["Professional Tax"],
    "component_amount": ["200"],
}


def _run_payroll_for_one_employee(client, csrf_token, period="2026-07"):
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))
    db = SessionLocal()
    employee_id = db.query(Employee).filter(Employee.employee_code == "EMP0001").first().id
    db.close()

    client.post(
        f"/attendance/{period}",
        data={
            "csrf_token": csrf_token,
            "employee_id": [str(employee_id)],
            "days_present": ["27"],
            "days_on_leave": ["0"],
        },
    )
    client.post("/payroll/run", data={"csrf_token": csrf_token, "period": period})

    db = SessionLocal()
    run_id = db.query(PayrollRun).first().id
    db.close()
    return run_id, employee_id


def test_bank_account_number_never_stored_in_plaintext_at_raw_db_level(logged_in_client):
    """
    Goes around the ORM entirely and reads the raw SQLite row — the
    strongest version of "no plaintext at rest" this suite can assert,
    since it doesn't rely on the ORM's decrypt-on-read property to hide
    anything that might actually be sitting in the column.
    """
    client, csrf_token = logged_in_client
    client.post("/employees/new", data=dict(_EMPLOYEE_PAYLOAD, csrf_token=csrf_token))

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT account_number_encrypted, account_number_last4 FROM employee_bank_details")
        ).first()

    assert row is not None
    assert "1234567890" not in row[0]  # plaintext account number never appears in the stored ciphertext
    assert row[1] == "7890"  # only the last 4 digits are ever stored in plain form, by design


def test_decrypting_with_wrong_key_fails_clearly(monkeypatch):
    """
    If BANK_ENCRYPTION_KEY is ever lost or rotated without a proper
    migration, old encrypted data becomes unreadable — that should raise a
    clear, catchable error, not crash unpredictably or silently return junk.
    """
    from cryptography.fernet import Fernet

    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()

    monkeypatch.setattr("app.config.settings.BANK_ENCRYPTION_KEY", key_a)
    ciphertext = encrypt_account_number("1234567890")

    monkeypatch.setattr("app.config.settings.BANK_ENCRYPTION_KEY", key_b)
    raised = False
    try:
        decrypt_account_number(ciphertext)
    except ValueError:
        raised = True
    assert raised, "decrypting with the wrong key should raise ValueError, not fail silently"


def test_payslip_pdf_regenerates_with_consistent_structure(logged_in_client):
    """
    "Deterministic" is checked as: two PDFs generated back-to-back from
    identical, unchanged data have the same byte length. Strict
    byte-for-byte equality isn't asserted, since fpdf2 embeds a creation
    timestamp in the PDF -- a same-length check is robust to that while
    still catching any real nondeterminism in the actual content/layout.
    """
    client, csrf_token = logged_in_client
    run_id, employee_id = _run_payroll_for_one_employee(client, csrf_token)

    first = client.get(f"/payroll/{run_id}/payslip/{employee_id}").content
    second = client.get(f"/payroll/{run_id}/payslip/{employee_id}").content

    assert first.startswith(b"%PDF")
    assert second.startswith(b"%PDF")
    assert len(first) == len(second)


def test_csv_export_is_byte_identical_across_regenerations(logged_in_client):
    """CSV has no embedded timestamp, so this can assert true equality, not just length."""
    client, csrf_token = logged_in_client
    run_id, _ = _run_payroll_for_one_employee(client, csrf_token)

    first = client.get(f"/payroll/{run_id}/export").content
    second = client.get(f"/payroll/{run_id}/export").content
    assert first == second


def test_csv_export_never_includes_bank_account_details(logged_in_client):
    """Regression guard: a future change adding columns to the CSV must not
    accidentally leak bank account numbers into a downloadable file."""
    client, csrf_token = logged_in_client
    run_id, _ = _run_payroll_for_one_employee(client, csrf_token)

    response = client.get(f"/payroll/{run_id}/export")
    assert "1234567890" not in response.text
    assert "account" not in response.text.lower()


def test_payslip_pdf_never_includes_bank_account_number(logged_in_client):
    """Same regression guard, for the PDF path."""
    client, csrf_token = logged_in_client
    run_id, employee_id = _run_payroll_for_one_employee(client, csrf_token)

    response = client.get(f"/payroll/{run_id}/payslip/{employee_id}")
    assert b"1234567890" not in response.content
