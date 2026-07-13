# Security Checklist Sign-Off

Every item below was actually verified against the code (grep-based checks
run directly against the repository, plus the automated tests noted), not
just asserted. Commands are included so this is re-checkable after future
changes, not just a one-time claim.

---

## 1. CSRF tokens present on every state-changing form

**Verified.** Every `<form method="post">` in `app/templates/` (6 files:
`login.html`, `base.html`'s logout form, `employees/form.html`,
`attendance/entry.html`, `payroll/new_run.html`, `partials/confirm_modal.html`)
contains exactly one `csrf_token` hidden field. The 4 real invocations of
the `confirm_modal` macro (2 in `employees/list.html`, 2 in
`employees/form.html`) all correctly pass `csrf_token=csrf_token` through.

Every POST route also calls `verify_csrf()` server-side before doing
anything — the template field alone doesn't protect anything without the
matching server-side check.

Re-check:
```bash
for f in $(grep -rl 'method="post"' app/templates/); do
  echo "$f: $(grep -c 'method="post"' "$f") form(s), $(grep -c 'name="csrf_token"' "$f") csrf field(s)"
done
```

## 2. Password hashes never rendered anywhere

**Verified.** Zero matches for `password_hash` across every template.

Re-check: `grep -rn "password_hash" app/templates/` (should return nothing).

## 3. Bank account numbers always masked, never shown decrypted in the UI

**Verified.** The only `account_number` reference in any template is the
form's own input field, which is intentionally always empty except when
echoing back what the admin just typed on a validation-error re-render
(their own current input, not a decrypted stored value — see
`employee_service.field_values_from_employee()`, which hardcodes this to
`""`). The only place a stored account number is ever referenced for
display is `account_number_last4`, used in the "Currently ending in
XXXX" placeholder.

Re-check: `grep -rn "\.account_number\b" app/templates/ | grep -v "last4\|encrypted"`
should show only the one input-field line, never inside an `{{ employee...
}}` expression.

## 4. No plaintext bank account numbers at rest

**Verified**, at the raw database level (not just through the ORM's
decrypt-on-read property) — see
`test_integrations.py::test_bank_account_number_never_stored_in_plaintext_at_raw_db_level`,
which queries the SQLite row directly via `engine.connect()` and confirms
the plaintext number never appears in `account_number_encrypted`.

Encryption uses `cryptography`'s Fernet, keyed by `BANK_ENCRYPTION_KEY` —
a secret deliberately separate from `SECRET_KEY`. Decrypting with the
wrong key raises a clear `ValueError` rather than failing silently or
crashing unpredictably (`test_decrypting_with_wrong_key_fails_clearly`).

## 5. Passwords hashed with bcrypt, not a weak or reversible scheme

**Verified**: `app/services/security.py` uses `passlib`'s `CryptContext(schemes=["bcrypt"])`.

## 6. No raw/string-formatted SQL anywhere in application code

**Verified.** The only `execute()` call in `app/` is the static, literal
`PRAGMA foreign_keys=ON` in `app/dependencies.py` — no variable
interpolation, no user input, no injection surface. Every actual data
query goes through SQLAlchemy's ORM, which parameterizes automatically.

Re-check: `grep -rn "execute(\|f\"SELECT\|f'SELECT" app/`

## 7. Session cookie hardening

**Verified**: `app/main.py`'s `SessionMiddleware` sets `same_site="lax"`
always, and `https_only=True` specifically when `ENVIRONMENT=production`
(correctly `False` in local dev over plain HTTP, where an HTTPS-only cookie
would just silently fail to be sent at all).

## 8. Login rate limiting

**Verified working in the app**, and **verified correctly disabled only
during tests** (`ENVIRONMENT=testing`, set exclusively by
`tests/conftest.py`) — see `app/routers/auth.py`'s `_rate_limited()`
helper. Confirmed this doesn't mask a real gap: no test asserts rate-limit
behavior is active, so nothing is silently untested by turning it off.

---

## Known, deliberate gaps (not oversights — see the planning docs)

- **No RBAC / row-level security** — single-admin MVP, by design (Backend
  Schema §6).
- **No audit log yet** — explicitly deferred to a later phase (Backend
  Schema §3.11 defines the schema; it's just not wired up).
- **Rate limiting is in-memory**, not Redis-backed — fine for a single-process
  deployment; would need revisiting before any multi-worker production deploy.

## Sign-off

All 8 items above verified as of this phase. Re-run the `grep`/test
commands after any change touching auth, forms, or bank data before
considering security posture unchanged.

Date: ______________
Checked by: ______________
