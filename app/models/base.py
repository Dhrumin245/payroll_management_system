from sqlalchemy.orm import declarative_base

# Shared by every model. Alembic's env.py imports Base.metadata (via
# app.models) to know what tables should exist — see migrations/env.py.
Base = declarative_base()
