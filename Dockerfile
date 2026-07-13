# Matches the Python version this project has been developed and tested
# against locally (3.10) -- deliberately not jumping to a newer minor
# version here, to avoid "works on my machine, breaks in the container"
# surprises for a detail that gains nothing at this project's scale.
FROM python:3.10-slim

WORKDIR /app

# No system-level packages needed beyond what pip provides -- this is
# exactly the payoff of the TRD's fpdf2-over-WeasyPrint decision (fpdf2 is
# pure Python; WeasyPrint would need Pango/Cairo/GDK-pixbuf installed here).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Shell form (not JSON array form) deliberately, so ${PORT:-8000} actually
# gets substituted -- most hosting platforms (Render, Railway, Fly.io)
# assign a dynamic port via $PORT and expect the app to bind to it.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
