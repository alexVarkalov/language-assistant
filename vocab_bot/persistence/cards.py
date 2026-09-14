from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vocab_bot.persistence.models import CardRecord
from vocab_bot.persistence.types import Card
from vocab_bot.persistence.utils import to_card, utc_now


class CardStore:
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
            stmt = pg_insert(CardRecord).values(
                user_id=user_id,
                source_lang=source_lang,
                target_lang=target_lang,
                source_text=source_text,
                target_text=target_text,
                ease_factor=ease_factor,
                interval_days=interval_days,
                repetition=repetition,
                next_review_at=next_review_at.astimezone(UTC).replace(microsecond=0),
                awaiting_grade=False,  # legacy chat-review column, kept at its default
                created_at=utc_now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "source_lang", "target_lang", "source_text"],
                set_={
                    "target_text": stmt.excluded.target_text,
                    "ease_factor": stmt.excluded.ease_factor,
                    "interval_days": stmt.excluded.interval_days,
                    "repetition": stmt.excluded.repetition,
                    "next_review_at": stmt.excluded.next_review_at,
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

    async def insert_card_if_missing(
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
    ) -> bool:
        return await asyncio.to_thread(
            self._insert_card_if_missing_sync,
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

    def _insert_card_if_missing_sync(
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
    ) -> bool:
        with self._session_factory() as session:
            stmt = pg_insert(CardRecord).values(
                user_id=user_id,
                source_lang=source_lang,
                target_lang=target_lang,
                source_text=source_text,
                target_text=target_text,
                ease_factor=ease_factor,
                interval_days=interval_days,
                repetition=repetition,
                next_review_at=next_review_at.astimezone(UTC).replace(microsecond=0),
                awaiting_grade=False,  # legacy chat-review column, kept at its default
                created_at=utc_now(),
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["user_id", "source_lang", "target_lang", "source_text"],
            ).returning(CardRecord.id)
            result = session.execute(stmt)
            inserted = result.first() is not None
            session.commit()
            return inserted

    async def get_card(self, card_id: int, user_id: int) -> Card | None:
        return await asyncio.to_thread(self._get_card_sync, card_id, user_id)

    def _get_card_sync(self, card_id: int, user_id: int) -> Card | None:
        with self._session_factory() as session:
            record = session.scalar(select(CardRecord).where(CardRecord.id == card_id, CardRecord.user_id == user_id))
            return to_card(record) if record is not None else None

    async def list_due_cards_for_user(self, user_id: int, limit: int = 50) -> list[Card]:
        return await asyncio.to_thread(self._list_due_cards_for_user_sync, user_id, limit)

    def _list_due_cards_for_user_sync(self, user_id: int, limit: int) -> list[Card]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(CardRecord)
                .where(CardRecord.user_id == user_id, CardRecord.next_review_at <= utc_now())
                .order_by(CardRecord.next_review_at.asc())
                .limit(limit)
            ).all()
            return [to_card(record) for record in rows]

    async def count_due_cards_for_user(self, user_id: int) -> int:
        return await asyncio.to_thread(self._count_due_cards_for_user_sync, user_id)

    def _count_due_cards_for_user_sync(self, user_id: int) -> int:
        with self._session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(CardRecord)
                .where(CardRecord.user_id == user_id, CardRecord.next_review_at <= utc_now())
            )
            return int(count or 0)

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
            session.commit()

    async def count_due_cards_by_user(self) -> dict[int, int]:
        return await asyncio.to_thread(self._count_due_cards_by_user_sync)

    def _count_due_cards_by_user_sync(self) -> dict[int, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(CardRecord.user_id, func.count())
                .where(CardRecord.next_review_at <= utc_now())
                .group_by(CardRecord.user_id)
            ).all()
            return {int(user_id): int(count) for user_id, count in rows}
