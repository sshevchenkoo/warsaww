from pydantic import model_validator
from pydantic_settings import BaseSettings

# Signing key shipped as the local-dev default. It is public knowledge, so a
# production deploy that still uses it has forgeable session cookies — the
# validator below refuses to start in that case.
INSECURE_SESSION_SECRET = "dev-insecure-change-me"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/events"
    # Connection pool. pool_pre_ping checks a connection is alive before use so a
    # managed Postgres dropping idle connections doesn't surface as a mid-request
    # error; pool_recycle proactively retires connections before the server's
    # idle timeout. Size is modest — the API holds a connection per in-flight
    # request (and streaming /search holds one for the whole LLM stream).
    # Managed Postgres caps connections low (DO basic tier = 25). With 2 API
    # replicas the worst case is 2*(pool_size+max_overflow); keep it under the
    # cap with headroom for cronjobs + DO's own monitoring roles. /search now
    # releases its connection before the LLM stream (app.api.routes.search), so
    # connections are short-lived and this modest pool rarely saturates. For
    # heavier load put DigitalOcean's PgBouncer (transaction mode) in front and
    # set psycopg's prepare_threshold=None (transaction pooling breaks named
    # prepared statements).
    db_pool_size: int = 5
    db_max_overflow: int = 5     # 2 replicas * (5+5) = 20 < max_connections (25)
    db_pool_recycle: int = 1800  # seconds; recycle connections older than 30 min
    db_pool_pre_ping: bool = True
    # Backstop against a runaway/hung query holding a pooled connection (see
    # lock-short-transactions). Generous enough for normal OLTP + ingestion;
    # raise via env on the ingestion CronJobs if a future bulk op needs longer.
    db_statement_timeout_ms: int = 30000
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
    # Max cosine distance (voyage-3.5) for a card to count as a match. Candidates
    # farther than this are dropped, so an off-base query returns empty fast
    # instead of re-ranking junk. Relevant hits measure ~0.4–0.56, clearly
    # unrelated ones ~0.62+. Tune if real queries get wrongly dropped.
    search_max_distance: float = 0.62
    # Hybrid retrieval: fuse the semantic (pgvector) leg with a lexical
    # trigram (pg_trgm) leg via Reciprocal Rank Fusion. The lexical leg catches
    # exact proper nouns (artist/venue names) and typos that dense embeddings
    # miss — and isn't subject to `search_max_distance`, so a perfect name match
    # is never dropped. Flip off to fall back to pure semantic + filters (useful
    # for A/B against the previous behaviour).
    hybrid_search: bool = True

    # Auth: Google OAuth + signed-cookie sessions (no server-side state, so the
    # API stays stateless across replicas — every replica validates with the
    # same session_secret).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    session_secret: str = INSECURE_SESSION_SECRET  # signs the session cookie
    # Where the browser-facing app lives: the OAuth redirect URI is
    # f"{frontend_url}/auth/callback" and login redirects back here when done.
    frontend_url: str = "http://localhost:3000"
    # Secure cookies require HTTPS — off for local http dev, on in production.
    session_https_only: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _reject_insecure_prod_config(self) -> "Settings":
        """Fail fast when a production-shaped deploy still carries dev defaults.

        `session_https_only` is our production signal (secure cookies require
        HTTPS). In that mode a default signing key or wildcard CORS would be a
        silent security hole, so we refuse to boot rather than ship it."""
        if self.session_https_only:
            if self.session_secret == INSECURE_SESSION_SECRET:
                raise ValueError(
                    "session_secret is still the insecure dev default while "
                    "session_https_only is on. Set SESSION_SECRET to a strong "
                    "random value in production (e.g. `openssl rand -hex 32`)."
                )
            if "*" in self.cors_origins:
                raise ValueError(
                    "cors_origins contains '*' while session_https_only is on. "
                    "Pin CORS_ORIGINS to explicit frontend origins in production."
                )
        return self


settings = Settings()
