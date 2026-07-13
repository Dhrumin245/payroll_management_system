"""
CSV export for a payroll run summary (App Flow Screen 9's optional stretch
feature). Uses the standard library's csv module -- no need for pandas at
this scale, per the TRD.
"""
import csv
import io

from app.models import PayrollLineItem


def generate_payroll_csv(line_items: list) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee Code", "Employee Name", "Gross Pay", "Total Deductions", "Net Pay"])
    for item in line_items:  # type: PayrollLineItem
        writer.writerow(
            [
                item.employee_code_snapshot,
                item.employee_name_snapshot,
                item.gross_pay,
                item.total_deductions,
                item.net_pay,
            ]
        )
    return output.getvalue()
