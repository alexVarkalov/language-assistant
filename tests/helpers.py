from __future__ import annotations

from datetime import UTC, datetime

from vocab_bot.persistence import BotUser


def make_user(**overrides: object) -> BotUser:
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = {
        "telegram_id": 123,
        "username": "tester",
        "first_name": "Test",
        "last_name": "User",
        "language_code": "en",
        "preferred_locale": None,
        "timezone": "UTC",
        "preferred_source_lang": "EN",
        "preferred_target_lang": "RU",
        "is_allowed": True,
        "created_at": now,
        "updated_at": now,
        "last_seen_at": now,
    }
    defaults.update(overrides)
    return BotUser(**defaults)
