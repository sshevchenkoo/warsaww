import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
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
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_saved_user_item"),)


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
