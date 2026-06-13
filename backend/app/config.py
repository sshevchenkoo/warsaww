from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/events"
    anthropic_api_key: str | None = None  # None → SDK falls back to ANTHROPIC_API_KEY env var
    intent_model: str = "claude-haiku-4-5"
    rerank_model: str = "claude-sonnet-4-6"  # cheaper than Opus ($3/$15 vs $5/$25)
    apify_token: str | None = None  # for the facebook_events adapter
    voyage_api_key: str | None = None
    embedding_model: str = "voyage-3.5"  # changing it = re-embed the whole base
    # CORS origins allowed to call the API from a browser ("*" for local dev).
    cors_origins: list[str] = ["*"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
