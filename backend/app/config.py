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
    # Whether the app may run DDL (extensions, create_all, indexes) on startup
    # and before ingestion. True for local dev (the local role owns the schema).
    # In prod set DB_BOOTSTRAP=false so the runtime role can be a least-privilege
    # DML-only role (audit #4); schema is then managed by the admin-run
    # `make do-db-migrate` step instead.
    db_bootstrap: bool = True
    # Backstop against a runaway/hung query holding a pooled connection (see
    # lock-short-transactions). Generous enough for normal OLTP + ingestion;
    # raise via env on the ingestion CronJobs if a future bulk op needs longer.
    db_statement_timeout_ms: int = 30000
    anthropic_api_key: str | None = None  # None → SDK falls back to ANTHROPIC_API_KEY env var
    intent_model: str = "claude-haiku-4-5"
    rerank_model: str = "claude-sonnet-4-6"  # cheaper than Opus ($3/$15 vs $5/$25)
    # Explicit timeouts (seconds) for the two Anthropic calls on /search. The SDK
    # default is 10 minutes, so a hung intent parse or a stalled rerank stream
    # would otherwise pin a request — and its per-session rate-limit slot and the
    # browser's SSE connection — for that whole window. Intent is a short
    # non-streaming Haiku call; rerank is a seconds-long Sonnet stream, so it gets
    # more headroom. On timeout the call fails cleanly and /search degrades
    # (raw-text retrieval / raw-order cards) instead of hanging (app.llm.intent,
    # app.api.routes.search).
    intent_timeout_s: float = 15.0
    rerank_timeout_s: float = 120.0
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
    # Brute-force guard on the auth endpoints (login/register): max attempts per
    # client IP per minute, backed by the same Redis. Fail-open (cost/abuse
    # control, not a hard security boundary — see app.ratelimit).
    auth_attempts_per_minute: int = 10

    # Avatar upload. Reject anything larger than max_upload before processing so
    # a huge file can't exhaust memory; the image is then re-encoded to a small
    # square thumbnail, so what actually lands in the DB is tiny regardless of
    # the input. avatar_max_stored_bytes is the hard DB backstop (CHECK).
    avatar_max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB accepted at the door
    avatar_size_px: int = 256                        # output is avatar_size_px square
    avatar_jpeg_quality: int = 82
    avatar_max_stored_bytes: int = 512 * 1024        # DB CHECK ceiling (~15-25KB typical)
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
    # HNSW recall tuning for filtered vector search. With WHERE filters
    # (date/category/budget) pgvector post-filters the ef_search candidates, so
    # a selective filter can starve results. pgvector >= 0.8 fixes this with
    # iterative scan (re-probes beyond ef_search until `limit` rows pass the
    # filter); relaxed_order trades exact ordering for recall — fine here since
    # the LLM re-ranker reorders anyway. ef_search default is 40; 100 widens the
    # candidate pool. Applied per-query via SET LOCAL in retrieval.search.
    hnsw_ef_search: int = 100
    hnsw_iterative_scan: str = "relaxed_order"  # off | strict_order | relaxed_order

    # Auth: Google OAuth + signed-cookie sessions (no server-side state, so the
    # API stays stateless across replicas — every replica validates with the
    # same session_secret).
    google_client_id: str | None = None
    google_client_secret: str | None = None

    # Transactional email (Resend) for email verification. Without resend_api_key
    # sending is a no-op (logged), so local dev / an unconfigured deploy still
    # works — verification links just aren't delivered. email_from must be a
    # verified sender for your domain in production; the default is Resend's
    # shared onboarding sender, usable for testing only.
    resend_api_key: str | None = None
    email_from: str = "Warsaw Events <onboarding@resend.dev>"
    # Replies to verification emails go here (e.g. your personal inbox). The FROM
    # address must be a domain you verified in Resend — a @gmail.com can't be a
    # sender — so route replies to a Gmail via reply-to instead.
    email_reply_to: str | None = None
    # Email verification uses a short numeric code the user types back in (not a
    # magic link). The code is single-use, expires quickly, and is capped at a
    # few wrong attempts before a fresh one must be requested — the code space is
    # only ~1M wide, so expiry + attempt cap + the auth rate limit are what keep
    # it from being guessable.
    email_verify_code_ttl_minutes: int = 15
    email_verify_max_attempts: int = 5
    # When True, password login is refused until the email is verified. Default
    # off so email delivery problems can't lock users out during rollout.
    require_email_verification: bool = False
    # Product gate: when True, /search requires a logged-in, email-verified user.
    # Anonymous or unverified visitors can still browse the upcoming feed and
    # open item pages, but can't run prompt searches.
    require_verified_email_to_search: bool = True

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
