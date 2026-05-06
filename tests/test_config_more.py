from __future__ import annotations

import pytest

from vocab_bot.config import Settings


def test_settings_from_env_invalid_intervals_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("DUE_POLL_INTERVAL", "bad")
    monkeypatch.setenv("SHORT_REVIEW_INTERVAL_MINUTES", "bad")

    settings = Settings.from_env()

    assert settings.due_poll_interval == 45
    assert settings.short_review_interval_minutes == 10


def test_settings_from_env_invalid_plan_and_translator_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("DEEPL_PLAN", "nonsense")
    monkeypatch.setenv("TRANSLATOR", "other")

    settings = Settings.from_env()

    assert settings.deepl_plan == "free"
    assert settings.translator == "deepl"


def test_settings_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("DATABASE_URL", "   ")

    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        Settings.from_env()
