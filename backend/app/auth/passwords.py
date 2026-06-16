"""Password hashing for email/password accounts (bcrypt)."""

import bcrypt

# bcrypt only uses the first 72 bytes of a password; reject longer ones at the
# API layer so a too-long password isn't silently truncated.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False
