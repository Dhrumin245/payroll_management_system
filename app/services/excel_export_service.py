"""
Excel Export Service — Phase 14.

Generates multi-sheet .xlsx workbooks for payroll runs using openpyxl.
"""
import io
from decimal import Decimal
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import PayrollLineItem, PayrollRun
from app.services.period_utils import format_period_label

# ── Styling constants ─────────────────────────────────────────────────────

_HEADER_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_MONEY_FORMAT = '#,##0.00'
_TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="1B2A4A")
_SUBTITLE_FONT = Font(name="Calibri", bold=True, size=11, color="6B7280")


def _style_header_row(ws, col_count: int) -> None:
    for col in range(1, col_count + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _THIN_BORDER


def _auto_width(ws) -> None:
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)


def generate_payroll_excel(payroll_run: PayrollRun, line_items: List[PayrollLineItem]) -> bytes:
    """
    Generate a multi-sheet Excel workbook:
      Sheet 1: Summary — run metadata and totals
      Sheet 2: Employee Breakdown — per-employee line items with components
      Sheet 3: Statutory Summary — PF, ESI, PT totals per employee
    """
    wb = Workbook()

    # ── Sheet 1: Summary ──────────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = "Summary"

    period_label = format_period_label(payroll_run.period)

    # Title block
    ws_summary.merge_cells("A1:D1")
    title_cell = ws_summary["A1"]
    title_cell.value = f"Payroll Summary — {period_label}"
    title_cell.font = _TITLE_FONT

    ws_summary.merge_cells("A2:D2")
    subtitle_cell = ws_summary["A2"]
    subtitle_cell.value = f"Run Date: {payroll_run.run_date.strftime('%Y-%m-%d %H:%M')}"
    subtitle_cell.font = _SUBTITLE_FONT

    # Totals table
    summary_data = [
        ["Metric", "Value"],
        ["Period", period_label],
        ["Total Employees", payroll_run.employee_count],
        ["Total Gross Pay", float(payroll_run.total_gross)],
        ["Total Deductions", float(payroll_run.total_deductions)],
        ["Total Net Pay", float(payroll_run.total_net_pay)],
    ]
    for row_idx, row_data in enumerate(summary_data, start=4):
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws_summary.cell(row=row_idx, column=col_idx, value=val)
            if row_idx == 4:
                cell.font = _HEADER_FONT
                cell.fill = _HEADER_FILL
                cell.alignment = _HEADER_ALIGNMENT
            cell.border = _THIN_BORDER
            if isinstance(val, float):
                cell.number_format = _MONEY_FORMAT

    _auto_width(ws_summary)

    # ── Sheet 2: Employee Breakdown ───────────────────────────────────────
    ws_detail = wb.create_sheet("Employee Breakdown")

    # Collect all unique component names across all line items
    all_earning_names: list[str] = []
    all_deduction_names: list[str] = []
    for item in line_items:
        for comp in item.components:
            if comp.component_type == "earning" and comp.name not in all_earning_names:
                all_earning_names.append(comp.name)
            elif comp.component_type == "deduction" and comp.name not in all_deduction_names:
                all_deduction_names.append(comp.name)

    headers = (
        ["Employee Code", "Employee Name", "Days Present", "Days Leave"]
        + all_earning_names
        + ["Gross Pay"]
        + all_deduction_names
        + ["Total Deductions", "Net Pay"]
    )
    for col_idx, header in enumerate(headers, start=1):
        ws_detail.cell(row=1, column=col_idx, value=header)

    _style_header_row(ws_detail, len(headers))

    for row_idx, item in enumerate(line_items, start=2):
        comp_map = {c.name: float(c.amount) for c in item.components}

        row_data = [
            item.employee_code_snapshot,
            item.employee_name_snapshot,
            float(item.days_present_snapshot),
            float(item.days_on_leave_snapshot),
        ]
        for name in all_earning_names:
            row_data.append(comp_map.get(name, 0.0))
        row_data.append(float(item.gross_pay))
        for name in all_deduction_names:
            row_data.append(comp_map.get(name, 0.0))
        row_data.extend([float(item.total_deductions), float(item.net_pay)])

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws_detail.cell(row=row_idx, column=col_idx, value=val)
            cell.border = _THIN_BORDER
            if isinstance(val, float):
                cell.number_format = _MONEY_FORMAT

    _auto_width(ws_detail)

    # ── Sheet 3: Statutory Summary ────────────────────────────────────────
    ws_statutory = wb.create_sheet("Statutory Summary")

    statutory_names = ["Provident Fund (PF)", "Employee State Insurance (ESI)", "Professional Tax (PT)"]
    stat_headers = ["Employee Code", "Employee Name"] + statutory_names + ["Total Statutory"]
    for col_idx, header in enumerate(stat_headers, start=1):
        ws_statutory.cell(row=1, column=col_idx, value=header)

    _style_header_row(ws_statutory, len(stat_headers))

    for row_idx, item in enumerate(line_items, start=2):
        comp_map = {c.name: float(c.amount) for c in item.components}
        stat_values = [comp_map.get(name, 0.0) for name in statutory_names]
        stat_total = sum(stat_values)

        row_data = [item.employee_code_snapshot, item.employee_name_snapshot] + stat_values + [stat_total]
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws_statutory.cell(row=row_idx, column=col_idx, value=val)
            cell.border = _THIN_BORDER
            if isinstance(val, float):
                cell.number_format = _MONEY_FORMAT

    _auto_width(ws_statutory)

    # ── Output ────────────────────────────────────────────────────────────
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
