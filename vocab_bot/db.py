from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from vocab_bot.persistence import DEFAULT_REMINDERS_PER_DAY, BotUser, Card, PendingTranslation
from vocab_bot.persistence.cards import CardStore
from vocab_bot.persistence.models import Base
from vocab_bot.persistence.pending import PendingStore
from vocab_bot.persistence.users import UserStore

__all__ = ["BotUser", "Card", "Database", "PendingTranslation", "database_lifecycle"]


class Database(UserStore, PendingStore, CardStore):
    """PostgreSQL persistence via SQLAlchemy ORM; public methods stay async."""

    def __init__(self, url: str) -> None:
        self._engine: Engine = create_engine(
            url,
            future=True,
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, class_=Session)

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        Base.metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_locale VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS due_notified_at TIMESTAMP WITH TIME ZONE"))
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reminders_per_day INTEGER NOT NULL "
                    f"DEFAULT {DEFAULT_REMINDERS_PER_DAY}"
                )
            )


@asynccontextmanager
async def database_lifecycle(url: str):
    db = Database(url)
    await db.init()
    yield db
