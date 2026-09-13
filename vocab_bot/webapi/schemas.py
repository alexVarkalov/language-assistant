from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from vocab_bot.services import DueCard, GradeResult


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ErrorResponse(BaseModel):
    error: str
    message: str


class LangPair(BaseModel):
    source: str
    target: str


class MeResponse(BaseModel):
    telegram_id: int
    locale: str
    timezone: str
    lang_pair: LangPair
    due_count: int
    short_review_interval_minutes: int


class QueueCard(BaseModel):
    id: int
    direction: Literal["source", "target"]
    prompt_text: str
    prompt_lang: str
    answer_text: str
    answer_lang: str
    repetition: int
    interval_days: float
    next_review_at: datetime

    @field_serializer("next_review_at")
    def _serialize_next_review_at(self, value: datetime) -> str:
        return _iso_utc(value)

    @classmethod
    def from_due(cls, due: DueCard) -> QueueCard:
        return cls(
            id=due.card.id,
            direction=due.direction,
            prompt_text=due.prompt_text,
            prompt_lang=due.prompt_lang,
            answer_text=due.answer_text,
            answer_lang=due.answer_lang,
            repetition=due.card.repetition,
            interval_days=due.card.interval_days,
            next_review_at=due.card.next_review_at,
        )


class QueueResponse(BaseModel):
    cards: list[QueueCard]
    total_due: int


class GradeRequest(BaseModel):
    quality: Literal[0, 3, 5]


class GradeResponse(BaseModel):
    card_id: int
    next_review_at: datetime
    interval_days: float
    ease_factor: float
    repetition: int

    @field_serializer("next_review_at")
    def _serialize_next_review_at(self, value: datetime) -> str:
        return _iso_utc(value)

    @classmethod
    def from_result(cls, card_id: int, result: GradeResult) -> GradeResponse:
        return cls(
            card_id=card_id,
            next_review_at=result.next_review_at,
            interval_days=result.interval_days,
            ease_factor=result.ease_factor,
            repetition=result.repetition,
        )
