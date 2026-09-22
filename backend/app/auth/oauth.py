"""Google OAuth client (authlib). Identity comes from Google's OIDC endpoint, so
a Google sign-in never reaches us as a password. Email+password accounts are a
separate path and do store a bcrypt hash — see app/auth/passwords.py."""

from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
