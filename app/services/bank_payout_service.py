"""
Bank Payout Service — Phase 13.

Generates NEFT-format CSV files for batch payout uploads to the bank.
"""
import csv
import io
import logging
from typing import List

from app.models import PayrollLineItem

logger = logging.getLogger("app")


def generate_neft_csv(line_items: List[PayrollLineItem]) -> bytes:
    """
    Creates a CSV containing employee payment details, decrypting bank
    account numbers for batch NEFT payout.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Standard headers for payout files
    writer.writerow([
        "Employee Code",
        "Employee Name",
        "Account Holder Name",
        "Account Number",
        "IFSC Code",
        "Bank Name",
        "Net Pay",
    ])

    for item in line_items:
        emp = item.employee
        bank = emp.bank_details if (emp and emp.bank_details) else None

        holder = ""
        acc_num = ""
        ifsc = ""
        bank_name = ""

        if bank:
            holder = bank.account_holder_name or ""
            ifsc = bank.ifsc_code or ""
            bank_name = bank.bank_name or ""
            try:
                acc_num = bank.account_number or ""
            except Exception as e:
                logger.error(
                    "Failed to decrypt bank account number for employee %s (%s): %s",
                    item.employee_name_snapshot,
                    item.employee_code_snapshot,
                    str(e),
                )
                acc_num = "[DECRYPTION_ERROR]"

        writer.writerow([
            item.employee_code_snapshot,
            item.employee_name_snapshot,
            holder,
            acc_num,
            ifsc,
            bank_name,
            f"{item.net_pay:.2f}",
        ])

    return output.getvalue().encode("utf-8")
