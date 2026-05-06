from __future__ import annotations

from datetime import UTC, datetime

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    format_langs,
    format_user_datetime,
    format_user_display,
    format_user_timezone,
    parse_target_user_id,
    user_lang_pair,
    user_timezone,
)


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="PL",
        target_lang="RU",
        available_languages=frozenset({"PL", "RU"}),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
    )


def test_format_langs() -> None:
    assert format_langs("EN", "RU") == "EN→RU"


def test_user_lang_pair_prefers_user_over_settings() -> None:
    settings = _settings()

    user = make_user(preferred_source_lang=None, preferred_target_lang=None)
    assert user_lang_pair(user, settings) == ("PL", "RU")

    user = make_user(preferred_source_lang="EN", preferred_target_lang="PL")
    assert user_lang_pair(user, settings) == ("EN", "PL")


def test_user_timezone_falls_back_to_utc() -> None:
    assert user_timezone(make_user(timezone=None)).key == "UTC"
    assert user_timezone(make_user(timezone="Not/AZone")).key == "UTC"


def test_format_user_datetime_uses_user_timezone() -> None:
    when = datetime(2026, 5, 6, 8, 0, tzinfo=UTC)
    user = make_user(timezone="UTC")
    assert format_user_datetime(when, user) == "2026-05-06 08:00 UTC"


def test_format_user_timezone() -> None:
    assert format_user_timezone(make_user(timezone=None)) == "UTC"
    assert format_user_timezone(make_user(timezone="Europe/Warsaw")) == "Europe/Warsaw"


def test_parse_target_user_id() -> None:
    assert parse_target_user_id(None) is None
    assert parse_target_user_id([]) is None
    assert parse_target_user_id(["abc"]) is None
    assert parse_target_user_id(("42",)) == 42


def test_format_user_display() -> None:
    assert format_user_display(make_user(username="tester")) == "@tester"
    assert format_user_display(make_user(username="", first_name="A", last_name="B")) == "A B"
    assert format_user_display(make_user(username="", first_name="", last_name="")) == "no profile name"
