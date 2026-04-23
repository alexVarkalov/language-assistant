from __future__ import annotations

from datetime import datetime

from vocab_bot.db import Card, Database, PendingTranslation


class PendingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, pending: PendingTranslation) -> None:
        await self._db.insert_pending(pending)

    async def get(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        return await self._db.get_pending(pending_id, user_id)

    async def delete(self, pending_id: str, user_id: int) -> None:
        await self._db.delete_pending(pending_id, user_id)


class CardRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(
        self,
        *,
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
        return await self._db.upsert_card(
            user_id=user_id,
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=source_text,
            target_text=target_text,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetition=repetition,
            next_review_at=next_review_at,
        )

    async def get(self, card_id: int, user_id: int) -> Card | None:
        return await self._db.get_card(card_id, user_id)

    async def list_due(self, limit: int = 10) -> list[Card]:
        return await self._db.list_due_cards(limit)

    async def mark_awaiting(self, card_id: int, user_id: int, awaiting: bool) -> None:
        await self._db.mark_awaiting(card_id, user_id, awaiting)

    async def update_srs(
        self,
        *,
        card_id: int,
        user_id: int,
        ease_factor: float,
        interval_days: float,
        repetition: int,
        next_review_at: datetime,
    ) -> None:
        await self._db.update_card_srs(
            card_id=card_id,
            user_id=user_id,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetition=repetition,
            next_review_at=next_review_at,
        )
