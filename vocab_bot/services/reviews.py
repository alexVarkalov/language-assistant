from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from vocab_bot.persistence import Card
from vocab_bot.repositories import CardRepository
from vocab_bot.srs import SrsState, next_review_datetime

# A direction names the side the user has to recall, so "source" prompts with the target text.
Direction = Literal["source", "target"]
DIRECTIONS: tuple[Direction, ...] = ("source", "target")

# How a card is asked changes as the user learns it: first recognise the foreign word (prompt is
# foreign, answer is the user's own language), then both ways at random, and finally produce the
# foreign word from the native prompt, which is the harder direction.
ReviewStage = Literal["recognition", "mixed", "production"]

# Upper bounds on Card.repetition for the first two stages; anything above is "production".
RECOGNITION_MAX_REPETITION = 2
MIXED_MAX_REPETITION = 5


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class GradeResult:
    next_review_at: datetime
    ease_factor: float
    interval_days: float
    repetition: int


@dataclass(frozen=True)
class DueCard:
    card: Card
    direction: Direction
    prompt_text: str
    prompt_lang: str
    answer_text: str
    answer_lang: str


def pick_direction(rng: random.Random | None = None) -> Direction:
    chooser = rng.choice if rng is not None else random.choice
    return chooser(DIRECTIONS)


def review_stage(repetition: int) -> ReviewStage:
    """How well the user knows a card, from its successful-review streak."""
    if repetition <= RECOGNITION_MAX_REPETITION:
        return "recognition"
    if repetition <= MIXED_MAX_REPETITION:
        return "mixed"
    return "production"


def direction_for_card(card: Card, native_lang: str | None, rng: random.Random | None = None) -> Direction:
    """
    Pick which side of a card to ask for, based on how well the user knows it.

    Without a native language (or on a card where neither side is it) there is no foreign/native
    split to key on, so the direction stays random the way it always was.
    """
    stage = review_stage(card.repetition)
    if stage == "mixed" or native_lang is None:
        return pick_direction(rng)
    native = native_lang.upper()
    source_is_native = card.source_lang.upper() == native
    if source_is_native == (card.target_lang.upper() == native):
        return pick_direction(rng)
    # Recognition asks for the native side, production asks for the foreign one.
    answer_is_native = stage == "recognition"
    return "source" if source_is_native == answer_is_native else "target"


def build_due_card(card: Card, direction: Direction) -> DueCard:
    # "source" means the user must recall source_text, so the prompt shows the target side.
    if direction == "source":
        return DueCard(
            card=card,
            direction=direction,
            prompt_text=card.target_text,
            prompt_lang=card.target_lang,
            answer_text=card.source_text,
            answer_lang=card.source_lang,
        )
    return DueCard(
        card=card,
        direction=direction,
        prompt_text=card.source_text,
        prompt_lang=card.source_lang,
        answer_text=card.target_text,
        answer_lang=card.target_lang,
    )


class ReviewService:
    def __init__(
        self,
        card_repo: CardRepository,
        *,
        short_interval_minutes: int = 10,
        native_lang: str | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._card_repo = card_repo
        self._short_interval_minutes = max(1, short_interval_minutes)
        self._native_lang = native_lang
        self._rng = rng

    async def get_card_for_user(self, *, card_id: int, user_id: int) -> Card | None:
        return await self._card_repo.get(card_id, user_id)

    async def apply_grade(self, *, card_id: int, user_id: int, quality: int) -> GradeResult | None:
        card = await self._card_repo.get(card_id, user_id)
        if card is None:
            return None
        before = SrsState(card.ease_factor, card.interval_days, card.repetition)
        when, after = next_review_datetime(before, quality, _now(), self._short_interval_minutes)
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

    async def list_due_cards_for_user(
        self,
        *,
        user_id: int,
        limit: int = 50,
        first_card_id: int | None = None,
    ) -> list[DueCard]:
        cards = await self._card_repo.list_due_for_user(user_id, limit=limit)
        if first_card_id is not None:
            cards.sort(key=lambda card: card.id != first_card_id)
        return [build_due_card(card, direction_for_card(card, self._native_lang, self._rng)) for card in cards]

    async def count_due_for_user(self, *, user_id: int) -> int:
        return await self._card_repo.count_due_for_user(user_id)
