from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from vocab_bot.persistence import BotUser, Card, PendingTranslation
from vocab_bot.persistence.cards import CardStore
from vocab_bot.persistence.models import Base
from vocab_bot.persistence.pending import PendingStore
from vocab_bot.persistence.users import UserStore

__all__ = ["BotUser", "Card", "Database", "PendingTranslation", "database_lifecycle"]


class Database(UserStore, PendingStore, CardStore):
    """SQLite persistence via SQLAlchemy ORM; public methods stay async."""

    def __init__(self, path: str) -> None:
        self._path = str(Path(path).expanduser())
        self._engine: Engine = create_engine(
            f"sqlite:///{self._path}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, class_=Session)

    async def init(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        with self._engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self._engine)
        self._upgrade_sync()

    def _upgrade_sync(self) -> None:
        with self._engine.begin() as conn:
            user_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)")}
            if "timezone" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN timezone VARCHAR")
            if "preferred_source_lang" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN preferred_source_lang VARCHAR")
            if "preferred_target_lang" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN preferred_target_lang VARCHAR")
            pending_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pending)")}
            if "target_options" not in pending_columns:
                conn.exec_driver_sql("ALTER TABLE pending ADD COLUMN target_options VARCHAR NOT NULL DEFAULT ''")


@asynccontextmanager
async def database_lifecycle(path: str):
    db = Database(path)
    await db.init()
    yield db
