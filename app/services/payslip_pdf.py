"""
Payslip PDF generation via fpdf2 (TRD §3's decision: pure-Python, no
system-level install dependencies, unlike WeasyPrint). Built with fpdf2's
cell() API rather than its newer table() helper, since that's changed
across fpdf2 releases -- cell()-based layout has been stable since the
original PyFPDF lineage and is the safer bet here.

Uses new_x=/new_y= (fpdf2's current cursor-advance API) rather than the
older ln=True, which is deprecated as of fpdf2 2.5.2.

IMPORTANT: uses "Rs." rather than the Rupee sign (₹) throughout. fpdf2's
core fonts (Helvetica/Times/Courier) use Latin-1/WinAnsi encoding and don't
support that Unicode character -- rendering it would need a bundled TTF
Unicode font, which is more moving parts than an MVP needs. The web pages
use "₹" freely since browsers render UTF-8 without this constraint; only
the PDF path needs this workaround.
"""
from decimal import Decimal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.config import settings
from app.models import PayrollLineItem

# Shorthand: advance to the left margin, next line down -- fpdf2's
# recommended replacement for the deprecated ln=True.
_NEXT_LINE = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}


def _money(amount: Decimal) -> str:
    return f"Rs. {amount:,.2f}"


def generate_payslip_pdf(line_item: PayrollLineItem, period_label: str) -> bytes:
    """
    Builds a payslip PDF for one employee's result within one payroll run.

    Uses ONLY snapshotted fields -- employee_code_snapshot,
    employee_name_snapshot, the line item's own amounts, and its
    components -- never the live Employee record. That's what keeps a
    payslip for a past period accurate even if the employee's details have
    since changed (Backend Schema's snapshot principle, Section 1).
    """
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Letterhead ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, settings.COMPANY_NAME, **_NEXT_LINE)
    if settings.COMPANY_ADDRESS:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, settings.COMPANY_ADDRESS, **_NEXT_LINE)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Payslip", **_NEXT_LINE)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Pay Period: {period_label}", **_NEXT_LINE)
    pdf.ln(4)

    # --- Employee details (snapshotted fields only -- see docstring) ---
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, f"{line_item.employee_name_snapshot} ({line_item.employee_code_snapshot})", **_NEXT_LINE)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        6,
        f"Days Present: {line_item.days_present_snapshot}   Days on Leave: {line_item.days_on_leave_snapshot}",
        **_NEXT_LINE,
    )
    pdf.ln(4)

    earnings = [c for c in line_item.components if c.component_type == "earning"]
    deductions = [c for c in line_item.components if c.component_type == "deduction"]

    def _section(title: str, rows: list, total: Decimal) -> None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, title, **_NEXT_LINE)
        pdf.set_font("Helvetica", "", 10)
        for row in rows:
            pdf.cell(130, 6, row.name)
            pdf.cell(0, 6, _money(row.amount), align="R", **_NEXT_LINE)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(130, 7, f"Total {title}")
        pdf.cell(0, 7, _money(total), align="R", **_NEXT_LINE)
        pdf.ln(3)

    _section("Earnings", earnings, line_item.gross_pay)
    _section("Deductions", deductions, line_item.total_deductions)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(130, 10, "Net Pay")
    pdf.cell(0, 10, _money(line_item.net_pay), align="R", **_NEXT_LINE)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, "This is a system-generated payslip.", **_NEXT_LINE)

    # fpdf2's output() with no arguments returns a bytearray; bytes()
    # normalizes it regardless of the exact type across fpdf2 versions.
    return bytes(pdf.output())
