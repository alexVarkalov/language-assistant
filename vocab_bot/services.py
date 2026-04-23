from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from vocab_bot.config import Settings
from vocab_bot.db import Card, PendingTranslation
from vocab_bot.repositories import CardRepository, PendingRepository
from vocab_bot.srs import SrsState, next_review_datetime
from vocab_bot.translate import translate_text


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class GradeResult:
    next_review_at: datetime
    ease_factor: float
    interval_days: float
    repetition: int


class TranslationService:
    def __init__(self, settings: Settings, pending_repo: PendingRepository, card_repo: CardRepository) -> None:
        self._settings = settings
        self._pending_repo = pending_repo
        self._card_repo = card_repo

    async def translate_and_store_pending(
        self, *, user_id: int, text: str, client: httpx.AsyncClient
    ) -> PendingTranslation:
        translated = await translate_text(
            text=text,
            source_lang=self._settings.source_lang,
            target_lang=self._settings.target_lang,
            translator=self._settings.translator,
            deepl_api_key=self._settings.deepl_api_key,
            deepl_plan=self._settings.deepl_plan,
            client=client,
        )
        pending = PendingTranslation(
            id=uuid.uuid4().hex,
            user_id=user_id,
            source_lang=self._settings.source_lang,
            target_lang=self._settings.target_lang,
            source_text=text.strip(),
            target_text=translated,
        )
        await self._pending_repo.add(pending)
        return pending

    async def save_pending_as_card(self, *, pending_id: str, user_id: int) -> PendingTranslation | None:
        pending = await self._pending_repo.get(pending_id, user_id)
        if pending is None:
            return None
        first_review = _now() + timedelta(minutes=10)
        await self._card_repo.upsert(
            user_id=pending.user_id,
            source_lang=pending.source_lang,
            target_lang=pending.target_lang,
            source_text=pending.source_text,
            target_text=pending.target_text,
            ease_factor=2.5,
            interval_days=0.0,
            repetition=0,
            next_review_at=first_review,
        )
        await self._pending_repo.delete(pending_id, pending.user_id)
        return pending

    async def dismiss_pending(self, *, pending_id: str, user_id: int) -> None:
        await self._pending_repo.delete(pending_id, user_id)


class ReviewService:
    def __init__(self, card_repo: CardRepository) -> None:
        self._card_repo = card_repo

    async def get_card_for_user(self, *, card_id: int, user_id: int) -> Card | None:
        return await self._card_repo.get(card_id, user_id)

    async def apply_grade(self, *, card_id: int, user_id: int, quality: int) -> GradeResult | None:
        card = await self._card_repo.get(card_id, user_id)
        if card is None:
            return None
        before = SrsState(card.ease_factor, card.interval_days, card.repetition)
        when, after = next_review_datetime(before, quality, _now())
        await self._card_repo.update_srs(
            card_id=card.id,
            user_id=card.user_id,
            ease_factor=after.ease_factor,
            interval_days=after.interval_days,
            repetition=after.repetition,
            next_review_at=when,
        )
        return GradeResult(
            next_review_at=when,
            ease_factor=after.ease_factor,
            interval_days=after.interval_days,
            repetition=after.repetition,
        )

    async def list_due_cards(self, *, limit: int = 50) -> list[Card]:
        return await self._card_repo.list_due(limit=limit)

    async def mark_awaiting(self, *, card_id: int, user_id: int, awaiting: bool) -> None:
        await self._card_repo.mark_awaiting(card_id, user_id, awaiting)
