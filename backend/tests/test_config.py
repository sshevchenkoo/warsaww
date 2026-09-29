"""The production config validator: with session_https_only on, the app must
refuse to boot on a dev-default or short signing key, or on wildcard CORS.
No network / no DB."""

import pytest
from pydantic import ValidationError

from app.config import INSECURE_SESSION_SECRET, MIN_SESSION_SECRET_LENGTH, Settings

STRONG_SECRET = "a" * 64  # the length `openssl rand -hex 32` produces
PROD_ORIGINS = ["https://example.com"]


def _prod(**overrides) -> Settings:
    values = {
        "session_https_only": True,
        "session_secret": STRONG_SECRET,
        "cors_origins": PROD_ORIGINS,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_strong_prod_config_boots():
    assert _prod().session_secret == STRONG_SECRET


def test_minimum_length_secret_boots():
    _prod(session_secret="a" * MIN_SESSION_SECRET_LENGTH)


def test_dev_default_secret_is_refused():
    with pytest.raises(ValidationError, match="insecure dev default"):
        _prod(session_secret=INSECURE_SESSION_SECRET)


@pytest.mark.parametrize(
    "secret",
    ["...", "", "a" * (MIN_SESSION_SECRET_LENGTH - 1)],
    ids=["example-placeholder", "empty", "one-short"],
)
def test_short_secret_is_refused(secret):
    with pytest.raises(ValidationError, match="shorter than"):
        _prod(session_secret=secret)


def test_wildcard_cors_is_refused():
    with pytest.raises(ValidationError, match="cors_origins"):
        _prod(cors_origins=["*"])


def test_local_dev_keeps_its_defaults():
    # Without session_https_only the dev default key and "*" CORS stay allowed.
    s = Settings(
        _env_file=None,
        session_https_only=False,
        session_secret=INSECURE_SESSION_SECRET,
        cors_origins=["*"],
    )
    assert s.session_secret == INSECURE_SESSION_SECRET
