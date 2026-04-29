from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
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
                awaiting_grade=False,
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
                    "awaiting_grade": False,
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
            return to_card(record) if record is not None else None

    async def get_awaiting_card(self, user_id: int) -> Card | None:
        return await asyncio.to_thread(self._get_awaiting_card_sync, user_id)

    def _get_awaiting_card_sync(self, user_id: int) -> Card | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(CardRecord)
                .where(CardRecord.user_id == user_id, CardRecord.awaiting_grade.is_(True))
                .order_by(CardRecord.next_review_at.asc())
                .limit(1)
            )
            return to_card(record) if record is not None else None

    async def list_due_cards(self, limit: int = 10) -> list[Card]:
        return await asyncio.to_thread(self._list_due_cards_sync, limit)

    def _list_due_cards_sync(self, limit: int) -> list[Card]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(CardRecord)
                .where(CardRecord.awaiting_grade.is_(False), CardRecord.next_review_at <= utc_now())
                .order_by(CardRecord.next_review_at.asc())
                .limit(limit)
            ).all()
            return [to_card(record) for record in rows]

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
