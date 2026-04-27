from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PendingTranslation:
    id: str
    user_id: int
    source_lang: str
    target_lang: str
    source_text: str
    target_text: str
    target_options: tuple[str, ...]


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


@dataclass(frozen=True)
class BotUser:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    timezone: str | None
    preferred_source_lang: str | None
    preferred_target_lang: str | None
    is_allowed: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
