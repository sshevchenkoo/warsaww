"""Seed a couple of ready-to-use, pre-verified TEST users for local testing.

    docker compose ... exec api python -m app.seed_users

Creates login-ready accounts directly in the DB (bypassing the signup form and
email verification), already marked email_verified=True so they can use search
right away — no email delivery (Resend) needed locally. Idempotent: re-running
resets their password. For LOCAL/demo use only.

Credentials (log in by email):
    user1@test.com / 1234
    user2@test.com / 1234
"""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.auth.passwords import hash_password
from app.catalog.db import Base, SessionLocal, engine
from app.catalog.models import User
from app.config import settings

log = logging.getLogger(__name__)

# (email, password, display name)
TEST_USERS = [
    ("user1@test.com", "1234", "Test User 1"),
    ("user2@test.com", "1234", "Test User 2"),
]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Local dev bootstraps its own schema (prod does it via the admin migrate).
    if settings.db_bootstrap:
        Base.metadata.create_all(engine)

    with SessionLocal() as session:
        for email, password, name in TEST_USERS:
            pw_hash = hash_password(password)
            stmt = (
                pg_insert(User)
                .values(email=email, password_hash=pw_hash, name=name, email_verified=True)
                .on_conflict_do_update(
                    index_elements=["email"],
                    set_={"password_hash": pw_hash, "email_verified": True, "name": name},
                )
            )
            session.execute(stmt)
        session.commit()

    creds = ", ".join(f"{email}/{pw}" for email, pw, _ in TEST_USERS)
    log.info("Seeded %d verified test users (log in by email): %s", len(TEST_USERS), creds)


if __name__ == "__main__":
    main()
