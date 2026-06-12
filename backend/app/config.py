from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/events"
    anthropic_api_key: str | None = None  # None → SDK falls back to ANTHROPIC_API_KEY env var
    intent_model: str = "claude-haiku-4-5"
    rerank_model: str = "claude-opus-4-8"
    apify_token: str | None = None  # for the facebook_events adapter

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
