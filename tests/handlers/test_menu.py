from __future__ import annotations

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers.menu import (
    locale_menu_keyboard,
    settings_menu_keyboard,
    settings_menu_text,
)


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="EN",
        target_lang="RU",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
    )


def test_settings_menu_text_contains_current_values() -> None:
    user = make_user(preferred_locale="ru")
    text = settings_menu_text("ru", user, _settings())
    assert "EN↔RU" in text
    assert "ru" in text


def test_settings_menu_keyboard_has_expected_callbacks() -> None:
    keyboard = settings_menu_keyboard("en")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["menu:locale"]


def test_locale_menu_marks_current_locale() -> None:
    keyboard = locale_menu_keyboard("en", "ru")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(label.startswith("✅ ru") for label in labels)
    assert labels[-1] == "Back"
