from passlib.context import CryptContext

# Framework-agnostic on purpose (TRD §6) — Werkzeug's hasher was Flask-specific;
# passlib does the same job regardless of web framework.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)
