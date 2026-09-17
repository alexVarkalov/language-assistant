from __future__ import annotations

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers.menu import (
    format_reminder_frequency,
    locale_menu_keyboard,
    reminders_menu_keyboard,
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
        wordbank_path=None,
    )


def test_settings_menu_text_contains_current_values() -> None:
    user = make_user(preferred_locale="ru")
    text = settings_menu_text("ru", user, _settings())
    assert "EN↔RU" in text
    assert "ru" in text
    assert "раз в день" in text
    assert "09:00" in text


def test_settings_menu_text_shows_reminder_times_in_user_timezone() -> None:
    user = make_user(timezone="Europe/Warsaw", reminders_per_day=3)
    text = settings_menu_text("en", user, _settings())
    assert "3 times a day" in text
    assert "09:00, 14:00, 19:00" in text
    assert "Europe/Warsaw" in text


def test_settings_menu_keyboard_has_expected_callbacks() -> None:
    keyboard = settings_menu_keyboard("en")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["menu:locale", "menu:reminders"]


def test_locale_menu_marks_current_locale() -> None:
    keyboard = locale_menu_keyboard("en", "ru")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(label.startswith("✅ ru") for label in labels)
    assert labels[-1] == "Back"


def test_reminders_menu_marks_current_option_and_lists_times() -> None:
    keyboard = reminders_menu_keyboard("en", 2)
    rows = keyboard.inline_keyboard
    labels = [button.text for row in rows for button in row]
    callbacks = [button.callback_data for row in rows for button in row]
    assert labels[:3] == [
        "once a day (09:00)",
        "✅ 2 times a day (09:00, 19:00)",
        "3 times a day (09:00, 14:00, 19:00)",
    ]
    assert callbacks == ["menu:set_reminders:1", "menu:set_reminders:2", "menu:set_reminders:3", "menu:open"]
    assert labels[-1] == "Back"


def test_format_reminder_frequency_uses_plural_forms() -> None:
    assert format_reminder_frequency("en", 1) == "once a day"
    assert format_reminder_frequency("ru", 1) == "раз в день"
    assert format_reminder_frequency("ru", 2) == "2 раза в день"
    assert format_reminder_frequency("ru", 3) == "3 раза в день"
