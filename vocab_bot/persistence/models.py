from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_source_lang: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_target_lang: Mapped[str | None] = mapped_column(String, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PendingRecord(Base):
    __tablename__ = "pending"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_lang: Mapped[str] = mapped_column(String, nullable=False)
    target_lang: Mapped[str] = mapped_column(String, nullable=False)
    source_text: Mapped[str] = mapped_column(String, nullable=False)
    target_text: Mapped[str] = mapped_column(String, nullable=False)
    target_options: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CardRecord(Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("user_id", "source_lang", "target_lang", "source_text"),
        Index("idx_cards_due", "user_id", "next_review_at", "awaiting_grade"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_lang: Mapped[str] = mapped_column(String, nullable=False)
    target_lang: Mapped[str] = mapped_column(String, nullable=False)
    source_text: Mapped[str] = mapped_column(String, nullable=False)
    target_text: Mapped[str] = mapped_column(String, nullable=False)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    repetition: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    awaiting_grade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
