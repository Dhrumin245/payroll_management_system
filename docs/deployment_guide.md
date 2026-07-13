# Deployment Guide

This is the one part of the project that genuinely needs a human at a
keyboard clicking through a hosting provider's dashboard — no amount of
code can do that step. Everything *up to* that point (Dockerfile,
`docker-compose.yml`, CI) is already built and verified; this document is
the walkthrough for the rest, using **Render** as the concrete example
(free tier, managed Postgres, deploys straight from a Dockerfile). Railway
and Fly.io both work too — same Dockerfile, different dashboard — noted
briefly at the end.

---

## 0. Before you start

Generate the two secrets you'll need (run locally):
```bash
python -c "import secrets; print(secrets.token_hex(32))"        # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # BANK_ENCRYPTION_KEY
```
Save both somewhere — you'll paste them into Render's dashboard, not into any file that gets committed.

Push this project to a GitHub repository if it isn't already there — Render deploys from a connected GitHub repo.

## 1. Test the container locally first

Don't debug container issues for the first time on a live platform. From the project root:
```bash
export BANK_ENCRYPTION_KEY=<paste the key you generated above>
docker compose up --build
```
Visit `http://localhost:8000` — you should reach the login page, exactly like running `uvicorn` directly, except now against Postgres instead of SQLite. Confirm:
```bash
docker compose exec app python -m app.cli create-admin
docker compose exec app python -m app.cli seed-demo
```
then log in and click through the full flow once. `docker compose down` when done (add `-v` to also wipe the Postgres volume for a clean slate).

## 2. Create the Postgres database on Render

1. Render dashboard → **New** → **PostgreSQL**.
2. Name it (e.g. `payroll-db`), pick the free tier, create it.
3. Once provisioned, copy the **Internal Database URL** — this is what `DATABASE_URL` will be set to. (Internal, not External — the web service and database live on the same network.)

## 3. Create the web service

1. Render dashboard → **New** → **Web Service** → connect the GitHub repo.
2. Runtime: **Docker** (Render detects the `Dockerfile` automatically).
3. Instance type: free tier is fine for a demo.
4. **Environment Variables** — add each of these:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Internal Database URL from step 2 |
   | `SECRET_KEY` | the value you generated in step 0 |
   | `BANK_ENCRYPTION_KEY` | the value you generated in step 0 |
   | `ENVIRONMENT` | `production` |
   | `COMPANY_NAME` | whatever you want on payslips |
   | `COMPANY_ADDRESS` | whatever you want on payslips |

5. Deploy. Watch the build log — first build takes a few minutes.

## 4. Run migrations and seed the first admin

The Dockerfile's `CMD` only starts the app — it doesn't run migrations automatically (see the comment in `docker-compose.yml` on why: auto-migrate-on-boot gets risky the moment more than one instance could start at once). Do it once, explicitly, via Render's **Shell** tab on the web service:
```bash
alembic upgrade head
python -m app.cli create-admin
python -m app.cli seed-demo   # optional, fictional demo data
```

## 5. Confirm it actually works

Visit the `.onrender.com` URL Render gives you. Confirm:
- The padlock/HTTPS is there (Render provides this automatically — nothing to configure).
- You're redirected to `/login` with no prior session.
- Full flow end to end: log in → add an employee → enter attendance → run payroll → download a payslip.

That last step is this phase's actual exit criteria — if it works from a browser that's never touched this app before, deployment is done.

## 6. Add the CI badge to the README

Once this is pushed to GitHub and the Actions workflow has run at least once, replace the placeholder in `README.md`'s badge line with your actual `USERNAME/REPO`.

## 7. Redeploying later

Render redeploys automatically on every push to the connected branch. If a future change adds a new migration, re-run `alembic upgrade head` via the Shell tab after that deploy finishes — migrations are deliberately not automatic (step 4's reasoning applies to every future deploy too, not just the first one).

---

## Alternatives (same Dockerfile, different dashboard)

- **Railway** — `New Project` → `Deploy from GitHub repo` → it detects the Dockerfile automatically; add a Postgres plugin from Railway's marketplace, same environment variables as above.
- **Fly.io** — `fly launch` in the project root detects the Dockerfile; `fly postgres create` for the database; `fly secrets set KEY=value` for each environment variable instead of a dashboard form.

Whichever platform, the Dockerfile, migrations-as-a-separate-step, and environment variable list are identical — only the clicking (or CLI) differs.
