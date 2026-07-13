# Payroll Management System

![Tests](https://github.com/USERNAME/REPO/actions/workflows/tests.yml/badge.svg)
<!-- Replace USERNAME/REPO above once this is pushed to GitHub -- see docs/deployment_guide.md §6 -->

A self-directed Python/FastAPI portfolio project. The full planning set (PRD,
TRD, App Flow, UI/UX Brief, Backend Schema, Implementation Plan) was produced
before any code — this repo follows that plan phase by phase.

## Setup

This needs internet access to install dependencies, which isn't available in
the sandbox this was scaffolded in — run these steps on your own machine.

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in real values, see comments in the file
                               # (COMPANY_NAME/COMPANY_ADDRESS show up on every payslip)
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000 — you'll be redirected to `/login`.
Interactive API docs are automatically available at http://127.0.0.1:8000/docs.

### Database & sample data

```bash
alembic upgrade head              # builds the full schema (users through payslips)
python -m app.cli create-admin    # prompts for username + password
python -m app.cli seed-demo       # optional: adds 4 fictional sample employees
```

Then log in at `/login` with that username/password to reach the placeholder Dashboard.

## Running tests

```bash
pytest --cov=app
```

Tests run against a dedicated `test.db` (see `tests/conftest.py`), never
your real `dev.db` — earlier versions of this project didn't have that
isolation and `pytest` would silently wipe your dev database's tables. If
you hit `no such table: users` after running tests, see "Recovering a wiped
dev.db" below.

## Recovering a wiped dev.db

If your `dev.db` ever ends up with no tables (Alembic thinks you're fully
migrated, but queries fail with `no such table: ...`), the fastest fix is a
clean rebuild:

```bash
rm dev.db                         # Windows: del dev.db
alembic upgrade head
python -m app.cli create-admin
python -m app.cli seed-demo       # optional
```


## Project structure

```
app/
  main.py         FastAPI app instance, middleware, routers, exception handlers
  config.py       Settings loaded from environment variables
  dependencies.py DB session (incl. SQLite FK-enforcement pragma), rate limiter, auth
  exceptions.py   NotAuthenticatedException -> redirect-to-login
  flash.py        Manual flash-message helper (no Flask-style flash() built in)
  templating.py   Jinja2 render() wrapper — auto-injects flashes + CSRF token
  cli.py          Typer CLI (create-admin, seed-demo)
  models/         SQLAlchemy models — one file per table/table-group
  services/       Framework-free logic: security (hashing), csrf, encryption
                  (bank account numbers), payroll_engine (the core math),
                  payroll_service (persistence/orchestration), payslip_pdf,
                  payroll_csv, dashboard_service, attendance_service, period_utils
  routers/        FastAPI routers (auth, employees, attendance, payroll)
  templates/
    base.html         Authenticated shell: navbar, flash area, content block
    auth_base.html     Lighter shell for Login + error pages (no navbar)
    dashboard.html      Summary cards, quick actions, recent runs (real data)
    login.html
    employees/, attendance/, payroll/    per-feature templates
    errors/404.html, errors/500.html
    partials/confirm_modal.html   Reusable Deactivate/Reactivate modal
  static/
    css/app.css     Design tokens + component styles (UI/UX Brief §§3-10)
    js/nav.js       Hamburger nav toggle (<768px)
    js/modal.js     Modal open/close + Escape-to-close
    js/dynamic_rows.js   Add/remove salary component rows
tests/
docs/
  manual_qa_checklist.md    Every App Flow screen's states, one checkbox each
  security_checklist.md     Verified (not just asserted) security posture
migrations/       Alembic — 0001 (users) through 0007 (users -> employees FK)
```

## Deployment

```bash
docker compose up --build   # app + Postgres locally, for container parity testing
```
For an actual public deployment (Render/Railway/Fly.io, all Dockerfile-compatible),
see `docs/deployment_guide.md` for the concrete, step-by-step walkthrough —
including the secrets you need to generate and why migrations are run as a
deliberate separate step rather than automatically on every container boot.

## Status

- [x] Phase 0 — Setup & Environment
- [x] Phase 1 — Authentication
- [x] Phase 2 — Database
- [x] Phase 3 — Core UI
- [x] Phase 4 — Main Features
  - [x] 4a — Employee Management
  - [x] 4b — Attendance
  - [x] 4c — Payroll Engine & Run
  - [x] 4d — Reports & Payslips
- [x] Phase 5 — Integrations
- [x] Phase 6 — Testing
- [x] Phase 7 — Deployment
- [ ] Phase 8 — Final Polish

**Phase 7 note:** the Dockerfile, docker-compose.yml, and CI workflow are
built and verified (config correctness, image build logic, no SQLite-only
code paths leaking into the Postgres path). The actual "click through a
hosting dashboard" step is documented in `docs/deployment_guide.md` but,
unavoidably, needs a human to actually do it — that part isn't something
that can be built in advance.

**Phase 6 note:** also wired the Dashboard to real data — Phase 3 shipped
it with hardcoded placeholders and no later phase explicitly came back for
it, so `/dashboard` was showing fake numbers until now. See
`docs/manual_qa_checklist.md` and `docs/security_checklist.md` for this
phase's other deliverables.

**Phase 5 note:** the PDF path, CSV export, and bank-detail encryption were
already built during 4a/4d rather than deferred — Phase 5 added the
verification the Implementation Plan calls for that wasn't yet explicit:
no plaintext bank data at the raw DB level (not just through the ORM), a
clear error if the encryption key is ever wrong, and consistent PDF/CSV
regeneration from the same data. See `tests/test_integrations.py`.

**Phase 4 is complete** — the full MVP feature set (employees, attendance,
payroll runs, payslips, reports) works end to end.
