from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class PendingTranslation:
    id: str
    user_id: int
    source_lang: str
    target_lang: str
    source_text: str
    target_text: str


@dataclass(frozen=True)
class Card:
    id: int
    user_id: int
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    ease_factor: float
    interval_days: float
    repetition: int
    next_review_at: datetime
    awaiting_grade: bool


class Base(DeclarativeBase):
    pass


class PendingRecord(Base):
    __tablename__ = "pending"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_lang: Mapped[str] = mapped_column(String, nullable=False)
    target_lang: Mapped[str] = mapped_column(String, nullable=False)
    source_text: Mapped[str] = mapped_column(String, nullable=False)
    target_text: Mapped[str] = mapped_column(String, nullable=False)
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


class Database:
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

    async def insert_pending(self, pending: PendingTranslation) -> None:
        await asyncio.to_thread(self._insert_pending_sync, pending)

    def _insert_pending_sync(self, pending: PendingTranslation) -> None:
        with self._session_factory() as session:
            session.add(
                PendingRecord(
                    id=pending.id,
                    user_id=pending.user_id,
                    source_lang=pending.source_lang,
                    target_lang=pending.target_lang,
                    source_text=pending.source_text,
                    target_text=pending.target_text,
                    created_at=_utc_now(),
                )
            )
            session.commit()

    async def get_pending(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        return await asyncio.to_thread(self._get_pending_sync, pending_id, user_id)

    def _get_pending_sync(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(PendingRecord).where(PendingRecord.id == pending_id, PendingRecord.user_id == user_id)
            )
            if record is None:
                return None
            return PendingTranslation(
                id=record.id,
                user_id=record.user_id,
                source_lang=record.source_lang,
                target_lang=record.target_lang,
                source_text=record.source_text,
                target_text=record.target_text,
            )

    async def delete_pending(self, pending_id: str, user_id: int) -> None:
        await asyncio.to_thread(self._delete_pending_sync, pending_id, user_id)

    def _delete_pending_sync(self, pending_id: str, user_id: int) -> None:
        with self._session_factory() as session:
            record = session.scalar(
                select(PendingRecord).where(PendingRecord.id == pending_id, PendingRecord.user_id == user_id)
            )
            if record is not None:
                session.delete(record)
            session.commit()

    async def upsert_card(
        self,
        user_id: int,
        source_lang: str,
        target_lang: str,
        source_text: str,
        target_text: str,
        ease_factor: float,
        interval_days: float,
        repetition: int,
        next_review_at: datetime,
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_card_sync,
            user_id,
            source_lang,
            target_lang,
            source_text,
            target_text,
            ease_factor,
            interval_days,
            repetition,
            next_review_at,
        )

    def _upsert_card_sync(
        self,
        user_id: int,
        source_lang: str,
        target_lang: str,
        source_text: str,
        target_text: str,
        ease_factor: float,
        interval_days: float,
        repetition: int,
        next_review_at: datetime,
    ) -> int:
        with self._session_factory() as session:
            stmt = sqlite_insert(CardRecord).values(
                user_id=user_id,
                source_lang=source_lang,
                target_lang=target_lang,
                source_text=source_text,
                target_text=target_text,
                ease_factor=ease_factor,
                interval_days=interval_days,
                repetition=repetition,
                next_review_at=next_review_at.astimezone(UTC).replace(microsecond=0),
                awaiting_grade=0,
                created_at=_utc_now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "source_lang", "target_lang", "source_text"],
                set_={
                    "target_text": stmt.excluded.target_text,
                    "ease_factor": stmt.excluded.ease_factor,
                    "interval_days": stmt.excluded.interval_days,
                    "repetition": stmt.excluded.repetition,
                    "next_review_at": stmt.excluded.next_review_at,
                    "awaiting_grade": 0,
                },
            )
            session.execute(stmt)
            card_id = session.scalar(
                select(CardRecord.id).where(
                    CardRecord.user_id == user_id,
                    CardRecord.source_lang == source_lang,
                    CardRecord.target_lang == target_lang,
                    CardRecord.source_text == source_text,
                )
            )
            session.commit()
            if card_id is None:
                msg = "failed to read card id after upsert"
                raise RuntimeError(msg)
            return int(card_id)

    async def get_card(self, card_id: int, user_id: int) -> Card | None:
        return await asyncio.to_thread(self._get_card_sync, card_id, user_id)

    def _get_card_sync(self, card_id: int, user_id: int) -> Card | None:
        with self._session_factory() as session:
            record = session.scalar(select(CardRecord).where(CardRecord.id == card_id, CardRecord.user_id == user_id))
            return _to_card(record) if record is not None else None

    async def list_due_cards(self, limit: int = 10) -> list[Card]:
        return await asyncio.to_thread(self._list_due_cards_sync, limit)

    def _list_due_cards_sync(self, limit: int) -> list[Card]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(CardRecord)
                .where(CardRecord.awaiting_grade == 0, CardRecord.next_review_at <= _utc_now())
                .order_by(CardRecord.next_review_at.asc())
                .limit(limit)
            ).all()
            return [_to_card(record) for record in rows]

    async def mark_awaiting(self, card_id: int, user_id: int, awaiting: bool) -> None:
        await asyncio.to_thread(self._mark_awaiting_sync, card_id, user_id, awaiting)

    def _mark_awaiting_sync(self, card_id: int, user_id: int, awaiting: bool) -> None:
        with self._session_factory() as session:
            record = session.scalar(select(CardRecord).where(CardRecord.id == card_id, CardRecord.user_id == user_id))
            if record is not None:
                record.awaiting_grade = bool(awaiting)
            session.commit()

    async def update_card_srs(
        self,
        card_id: int,
        user_id: int,
        ease_factor: float,
        interval_days: float,
        repetition: int,
        next_review_at: datetime,
    ) -> None:
        await asyncio.to_thread(
            self._update_card_srs_sync,
            card_id,
            user_id,
            ease_factor,
            interval_days,
            repetition,
            next_review_at,
        )

    def _update_card_srs_sync(
        self,
        card_id: int,
        user_id: int,
        ease_factor: float,
        interval_days: float,
        repetition: int,
        next_review_at: datetime,
    ) -> None:
        with self._session_factory() as session:
            record = session.scalar(select(CardRecord).where(CardRecord.id == card_id, CardRecord.user_id == user_id))
            if record is not None:
                record.ease_factor = ease_factor
                record.interval_days = interval_days
                record.repetition = repetition
                record.next_review_at = next_review_at.astimezone(UTC).replace(microsecond=0)
                record.awaiting_grade = False
            session.commit()


@asynccontextmanager
async def database_lifecycle(path: str):
    db = Database(path)
    await db.init()
    yield db


def _to_card(record: CardRecord) -> Card:
    return Card(
        id=record.id,
        user_id=record.user_id,
        source_text=record.source_text,
        target_text=record.target_text,
        source_lang=record.source_lang,
        target_lang=record.target_lang,
        ease_factor=record.ease_factor,
        interval_days=record.interval_days,
        repetition=record.repetition,
        next_review_at=record.next_review_at,
        awaiting_grade=bool(record.awaiting_grade),
    )
