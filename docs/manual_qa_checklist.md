# Manual QA Checklist

Derived from the App Flow document — every screen's Success/Error/Empty
state, one checkbox each. Items marked **[Auto]** already have an automated
test proving them (see the test file named); walking through them by hand
is optional confirmation, not required. Unmarked items need an actual click
through the running app — that's the point of this phase.

Reset to a clean slate before starting: `del dev.db` (Windows) then
`alembic upgrade head` and `python -m app.cli create-admin`.

---

## Screen 1 — Login

- [ ] Valid credentials → redirected to Dashboard **[Auto: test_auth.py]**
- [ ] Invalid username/password → generic "Invalid username or password.", password field cleared, username retained **[Auto]**
- [ ] Already logged in, visiting `/login` → redirected straight to Dashboard
- [ ] Empty username or password → browser-level `required` validation blocks submit

## Screen 2 — Dashboard

- [ ] Zero employees, zero runs → "No employees yet" banner + "No payroll runs yet" **[Auto: test_dashboard.py]**
- [ ] Active employee count reflects reality, not a placeholder **[Auto]**
- [ ] Recent Payroll Runs table appears once a run exists, links to that run's summary **[Auto]**
- [ ] Quick-action buttons (Add Employee / Enter Attendance / Run Payroll) all go somewhere real, not a 404

## Screen 3 — Employee List

- [ ] Zero employees at all → "You haven't added any employees yet." + CTA **[Auto: test_employees.py]**
- [ ] Filter/search matches nothing → "No employees found" + Clear filters link
- [ ] Search by name works
- [ ] Search by employee code works
- [ ] Status filter (Active/Inactive/All) works
- [ ] Deactivate → confirmation modal → status badge updates in place **[Auto]**
- [ ] Reactivate → confirmation modal → status badge updates in place **[Auto]**
- [ ] Modal Cancel / clicking outside / Escape key all close without submitting

## Screen 4 — Add Employee

- [ ] Valid submission → redirects to the new Employee Detail page, flash success **[Auto]**
- [ ] Duplicate employee code → inline error, form values preserved **[Auto]**
- [ ] Basic Pay = 0 → inline error "must be greater than 0" **[Auto]**
- [ ] Missing required field (name/designation/joining date) → inline error **[Auto]**
- [ ] "+ Add allowance" / "+ Add deduction" rows actually add/remove correctly in the browser
- [ ] Employee Code is pre-filled with a sensible suggested value (EMP000N)
- [ ] Bank Account Number field only requires Account Holder Name if filled in **[Auto]**

## Screen 5 — Employee Detail

- [ ] Editing and saving updates the record, flash success
- [ ] Bank account number field shows "Currently ending in XXXX — leave blank to keep unchanged" and leaving it blank does NOT wipe the stored number **[Auto]**
- [ ] Unknown employee ID → styled 404 page **[Auto]**
- [ ] Attendance History tab shows "No attendance records yet" for a brand-new employee
- [ ] Payroll History tab shows "hasn't been included in a payroll run yet" for a brand-new employee
- [ ] Deactivate/Reactivate buttons work the same as on the List screen

## Screen 6 — Attendance Entry

- [ ] Zero active employees → "No active employees to record attendance for." + Add Employee link **[Auto: test_attendance.py]**
- [ ] Save populates all rows, "Saved" badge appears **[Auto]**
- [ ] Revisiting a saved period shows the previously entered values **[Auto]**
- [ ] Days present + leave exceeding working days → inline error, nothing saved **[Auto]**
- [ ] Period selector actually navigates between months in the browser
- [ ] Once payroll has been run for a period, the form is fully read-only (inputs disabled, Save button hidden) **[Auto]**

## Screen 7 — Payroll History

- [ ] Zero runs → "No payroll has been run yet." + CTA **[Auto: test_payroll.py]**
- [ ] Existing runs list with period, date, employee count, total net pay
- [ ] Clicking a run navigates to its Summary page

## Screen 8 — New Payroll Run

- [ ] Attendance incomplete → shows count of employees missing, Run button disabled, link to complete attendance **[Auto]**
- [ ] Attendance complete → shows "Attendance complete", Run button enabled
- [ ] Period already run → "already been processed" message, link to history, Run button disabled **[Auto]**
- [ ] Zero active employees → Run button disabled, "No active employees to process."
- [ ] Successful run redirects to that run's Summary page **[Auto]**

## Screen 9 — Payroll Run Summary

- [ ] Totals panel (employees / gross / deductions / net) matches the per-employee table's sum
- [ ] Per-employee table numbers are right-aligned, tabular, easy to scan
- [ ] "Download Payslip" produces a real PDF per employee **[Auto: test_payslips.py]**
- [ ] "Export Summary (CSV)" produces a real CSV **[Auto]**
- [ ] Unknown run ID → styled 404 page **[Auto]**

## Screen 10 — Payslip (file download)

- [ ] Opens/downloads as a real PDF, not an error page **[Auto]**
- [ ] Shows company name/address, employee name + code, earnings, deductions, net pay
- [ ] Numbers on the payslip match the Summary page exactly
- [ ] Editing the employee's name afterward does NOT change a previously generated payslip's data **[Auto]**

## Global states

- [ ] Hitting any protected page while logged out → redirected to `/login?next=...`, flash "Please log in to continue." **[Auto: test_auth.py, test_dashboard.py]**
- [ ] After logging in via a `next=` redirect, you land back where you were headed, not always the Dashboard
- [ ] Unknown route → styled 404 page, not a raw error **[Auto: test_ui_shell.py]**
- [ ] Flash messages are dismissible (× button) and auto-disappear
- [ ] Browser window narrower than 768px → nav collapses to a hamburger menu
- [ ] Logout actually clears the session (revisiting a protected page redirects to login) **[Auto: test_auth.py]**

---

## Sign-off

Once every box above is checked (or explicitly waived with a reason), Phase 6's manual QA pass is complete.

Date checked: ______________
Checked by: ______________
Notes / known issues: ______________
