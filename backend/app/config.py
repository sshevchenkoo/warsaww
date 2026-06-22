from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/events"
    anthropic_api_key: str | None = None  # None → SDK falls back to ANTHROPIC_API_KEY env var
    intent_model: str = "claude-haiku-4-5"
    rerank_model: str = "claude-sonnet-4-6"  # cheaper than Opus ($3/$15 vs $5/$25)
    apify_token: str | None = None  # for the facebook_events adapter
    ticketmaster_api_key: str | None = None  # Consumer Key for the Ticketmaster adapter
    voyage_api_key: str | None = None
    embedding_model: str = "voyage-3.5"  # changing it = re-embed the whole base
    # CORS origins allowed to call the API from a browser ("*" for local dev).
    cors_origins: list[str] = ["*"]

    # Redis (used for the per-session search rate limit). Inside compose/k8s the
    # host is `redis`, not localhost.
    redis_url: str = "redis://localhost:6379/0"
    search_daily_limit: int = 10  # searches allowed per session per day

    # Auth: Google OAuth + signed-cookie sessions (no server-side state, so the
    # API stays stateless across replicas — every replica validates with the
    # same session_secret).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    session_secret: str = "dev-insecure-change-me"  # signs the session cookie
    # Where the browser-facing app lives: the OAuth redirect URI is
    # f"{frontend_url}/auth/callback" and login redirects back here when done.
    frontend_url: str = "http://localhost:3000"
    # Secure cookies require HTTPS — off for local http dev, on in production.
    session_https_only: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
