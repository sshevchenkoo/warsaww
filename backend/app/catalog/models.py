import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.catalog.db import Base

EMBEDDING_DIM = 1024


class Item(Base):
    """Single entity for both events and permanent places."""

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(Text)  # 'event' | 'place'
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    price_from: Mapped[float | None] = mapped_column(Numeric)
    price_to: Mapped[float | None] = mapped_column(Numeric)
    image_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)  # canonical source after dedup
    source_url: Mapped[str | None] = mapped_column(Text)
    # extra (source, source_url) pairs merged in by dedup from other sources:
    sources: Mapped[list | None] = mapped_column(JSONB)

    # events only:
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # permanent places only:
    is_permanent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    opening_hours: Mapped[dict | None] = mapped_column(JSONB)  # weekly schedule

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        # Bound the free-text discriminator so a typo can't write a junk kind.
        CheckConstraint("kind IN ('event', 'place')", name="ck_items_kind"),
        # Upsert key for ingestion: re-running a source updates, not duplicates.
        UniqueConstraint("source", "source_url", name="uq_items_source_url"),
        Index(
            "ix_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_items_starts_at", "starts_at"),
        Index("ix_items_category", "category"),
        # Trigram index (pg_trgm) backing the lexical leg of hybrid search —
        # accelerates word_similarity / `<%` matches on the card name. Requires
        # the pg_trgm extension; it is ensured (along with this index, for the
        # already-existing items table) in app.main._create_schema.
        Index(
            "ix_items_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class User(Base):
    """An authenticated user. Identity can come from Google (google_sub) or from
    an email + password (password_hash); email is the shared, unique identifier."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Google's stable user id — NULL for password-only accounts (UNIQUE still
    # holds; Postgres allows multiple NULLs).
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    # bcrypt hash — NULL for Google-only accounts.
    password_hash: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, unique=True)  # the login identifier
    # True once the email is confirmed (verification link, or a Google login,
    # which proves ownership). Password accounts start unverified.
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        # Trigram index so /users/search's `name ILIKE '%term%'` (leading
        # wildcard → can't use a btree) is index-accelerated. Needs pg_trgm.
        Index(
            "ix_users_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class SavedItem(Base):
    """A user's saved/favorite item (event or place)."""

    __tablename__ = "saved_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Indexed: Postgres doesn't index FK columns automatically; without it the
    # ON DELETE CASCADE from items (and any item_id lookup) is a seq scan.
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_saved_user_item"),)


class Friendship(Base):
    """A friendship between two users, modeled as a directed request that becomes
    mutual once accepted.

    - status 'pending':  requester asked addressee; awaiting their response.
    - status 'accepted': the two are friends (direction no longer matters).

    "Are A and B friends?" = an accepted row with {requester, addressee} == {A, B}
    in either direction. One row per ordered (requester, addressee) pair.
    """

    __tablename__ = "friendships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
        CheckConstraint("status IN ('pending', 'accepted')", name="ck_friendship_status"),
    )


class SharedEvent(Base):
    """One user sharing an item (event/place) with a friend. Shows up in the
    recipient's "shared with me" inbox."""

    __tablename__ = "shared_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Indexed FK (see SavedItem.item_id) — speeds the ON DELETE CASCADE from items.
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", "item_id", name="uq_share_once"),
    )


class UserAvatar(Base):
    """A user's uploaded avatar image, kept in its own table (not a column on
    `users`) so the blob never rides along on the many `SELECT ... FROM users`
    queries in the social layer. One row per user; the bytes are a small
    server-resized thumbnail, and a CHECK caps the size as a DB-level backstop."""

    __tablename__ = "user_avatars"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        # Hard ceiling on stored size — the app resizes well below this, but the
        # constraint guarantees a row can never bloat the table (audit-style
        # backstop). Keep in sync with settings.avatar_max_stored_bytes.
        CheckConstraint("octet_length(data) <= 524288", name="ck_user_avatars_size"),
    )


class IntentLog(Base):
    """Log of prompt parses: future fine-tuning dataset for a local model."""

    __tablename__ = "intent_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_prompt: Mapped[str] = mapped_column(Text)
    intent: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
