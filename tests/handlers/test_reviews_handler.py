from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest, Forbidden

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers.reviews import due_poll, due_summary_keyboard
from vocab_bot.services import DueSummary


def _settings(webapp_url: str | None = None) -> Settings:
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
        webapp_url=webapp_url,
    )


def _ctx(webapp_url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={"settings": _settings(webapp_url), "due_notification_service": AsyncMock()}
        ),
        bot=AsyncMock(),
    )


def test_due_summary_keyboard_without_webapp_is_none() -> None:
    assert due_summary_keyboard("en", _settings()) is None


def test_due_summary_keyboard_opens_app_at_root() -> None:
    keyboard = due_summary_keyboard("ru", _settings("https://vocab.example.com"))

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://vocab.example.com"
    assert button.callback_data is None


@pytest.mark.asyncio
async def test_due_poll_sends_one_summary_per_user_and_marks_notified() -> None:
    context = _ctx("https://vocab.example.com")
    notifier = context.application.bot_data["due_notification_service"]
    notifier.collect.return_value = [
        DueSummary(user=make_user(telegram_id=10, language_code="en"), due_count=1),
        DueSummary(user=make_user(telegram_id=20, preferred_locale="ru"), due_count=5),
    ]

    await due_poll(context)

    assert context.bot.send_message.await_count == 2
    first, second = context.bot.send_message.await_args_list
    assert first.kwargs["chat_id"] == 10
    assert "<b>1</b> card to review" in first.kwargs["text"]
    assert first.kwargs["reply_markup"].inline_keyboard[0][0].web_app.url == "https://vocab.example.com"
    assert second.kwargs["chat_id"] == 20
    assert "<b>5</b> карточек" in second.kwargs["text"]
    assert [call.args[0] for call in notifier.mark_notified.await_args_list] == [10, 20]


@pytest.mark.asyncio
async def test_due_poll_returns_when_collect_fails() -> None:
    context = _ctx()
    context.application.bot_data["due_notification_service"].collect.side_effect = RuntimeError("db")

    await due_poll(context)

    context.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_poll_does_not_mark_notified_when_send_fails() -> None:
    context = _ctx("https://vocab.example.com")
    notifier = context.application.bot_data["due_notification_service"]
    notifier.collect.return_value = [
        DueSummary(user=make_user(telegram_id=10), due_count=2),
        DueSummary(user=make_user(telegram_id=20), due_count=3),
    ]
    context.bot.send_message.side_effect = [RuntimeError("telegram down"), SimpleNamespace(message_id=2)]

    await due_poll(context)

    assert [call.args[0] for call in notifier.mark_notified.await_args_list] == [20]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [Forbidden("bot was blocked by the user"), BadRequest("Chat not found")])
async def test_due_poll_marks_unreachable_user_as_notified(error: Exception) -> None:
    context = _ctx("https://vocab.example.com")
    notifier = context.application.bot_data["due_notification_service"]
    notifier.collect.return_value = [DueSummary(user=make_user(telegram_id=10), due_count=2)]
    context.bot.send_message.side_effect = error

    await due_poll(context)

    notifier.mark_notified.assert_awaited_once_with(10)
