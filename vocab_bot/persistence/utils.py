from __future__ import annotations

from datetime import UTC, datetime

from vocab_bot.persistence.models import CardRecord, UserRecord
from vocab_bot.persistence.types import BotUser, Card


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def to_card(record: CardRecord) -> Card:
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


def to_user(record: UserRecord) -> BotUser:
    return BotUser(
        telegram_id=record.telegram_id,
        username=record.username,
        first_name=record.first_name,
        last_name=record.last_name,
        language_code=record.language_code,
        timezone=record.timezone,
        preferred_source_lang=record.preferred_source_lang,
        preferred_target_lang=record.preferred_target_lang,
        is_allowed=bool(record.is_allowed),
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_seen_at=record.last_seen_at,
    )
