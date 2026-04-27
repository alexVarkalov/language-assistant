from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from vocab_bot.persistence import Card
from vocab_bot.repositories import CardRepository
from vocab_bot.srs import SrsState, next_review_datetime


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class GradeResult:
    next_review_at: datetime
    ease_factor: float
    interval_days: float
    repetition: int


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
