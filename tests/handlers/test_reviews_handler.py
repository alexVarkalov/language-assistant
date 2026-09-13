from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import reviews as reviews_module
from vocab_bot.handlers.reviews import due_poll, due_review_keyboard
from vocab_bot.persistence.types import Card


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


def _card(card_id: int, user_id: int, source: str = "hello", target: str = "privet") -> Card:
    return Card(
        id=card_id,
        user_id=user_id,
        source_text=source,
        target_text=target,
        source_lang="EN",
        target_lang="RU",
        ease_factor=2.5,
        interval_days=1.0,
        repetition=1,
        next_review_at=datetime.now(tz=UTC),
        awaiting_grade=False,
    )


def _ctx(webapp_url: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(webapp_url),
                "review_service": AsyncMock(),
                "user_service": AsyncMock(),
            }
        ),
        bot=AsyncMock(),
    )


def test_due_review_keyboard_without_webapp_has_only_reveal() -> None:
    keyboard = due_review_keyboard("en", 7, "source", "EN", _settings())

    assert len(keyboard.inline_keyboard) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == "reveal:7:source"


def test_due_review_keyboard_with_webapp_adds_open_in_app_row() -> None:
    keyboard = due_review_keyboard("en", 7, "target", "RU", _settings("https://vocab.example.com"))

    assert len(keyboard.inline_keyboard) == 2
    button = keyboard.inline_keyboard[1][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://vocab.example.com/?card=7"
    assert button.callback_data is None


@pytest.mark.asyncio
async def test_due_poll_sends_open_in_app_button_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _ctx("https://vocab.example.com")
    context.application.bot_data["review_service"].list_due_cards.return_value = [_card(5, 10)]
    context.application.bot_data["user_service"].is_allowed.return_value = True
    context.application.bot_data["user_service"].get_user.return_value = make_user(telegram_id=10)
    context.bot.send_message.return_value = SimpleNamespace(message_id=1)
    monkeypatch.setattr(reviews_module, "pick_direction", lambda: "source")

    await due_poll(context)

    markup = context.bot.send_message.await_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[1][0].web_app.url == "https://vocab.example.com/?card=5"


@pytest.mark.asyncio
async def test_due_poll_returns_when_list_due_fails() -> None:
    context = _ctx()
    context.application.bot_data["review_service"].list_due_cards.side_effect = RuntimeError("db")

    await due_poll(context)

    context.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_poll_sends_once_per_user_and_marks_awaiting(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _ctx()
    review_service = context.application.bot_data["review_service"]
    user_service = context.application.bot_data["user_service"]
    review_service.list_due_cards.return_value = [_card(1, 10), _card(2, 10), _card(3, 20)]
    user_service.is_allowed.side_effect = [True, True]
    user_service.get_user.side_effect = [make_user(telegram_id=10), make_user(telegram_id=20)]
    context.bot.send_message.side_effect = [
        SimpleNamespace(message_id=101),
        SimpleNamespace(message_id=202),
    ]
    monkeypatch.setattr(reviews_module, "pick_direction", lambda: "source")

    await due_poll(context)

    assert context.bot.send_message.await_count == 2
    assert review_service.mark_awaiting.await_count == 2
    assert context.application.bot_data["awaiting_review_messages"][(10, 1)] == 101
    assert context.application.bot_data["awaiting_review_messages"][(20, 3)] == 202
    assert context.application.bot_data["awaiting_review_directions"][(10, 1)] == "source"


@pytest.mark.asyncio
async def test_due_poll_skips_disallowed_user() -> None:
    context = _ctx()
    review_service = context.application.bot_data["review_service"]
    user_service = context.application.bot_data["user_service"]
    review_service.list_due_cards.return_value = [_card(1, 10)]
    user_service.is_allowed.return_value = False

    await due_poll(context)

    context.bot.send_message.assert_not_awaited()
    review_service.mark_awaiting.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_poll_swallow_send_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _ctx()
    review_service = context.application.bot_data["review_service"]
    user_service = context.application.bot_data["user_service"]
    review_service.list_due_cards.return_value = [_card(1, 10)]
    user_service.is_allowed.return_value = True
    user_service.get_user.return_value = make_user(telegram_id=10)
    context.bot.send_message.side_effect = RuntimeError("telegram down")
    monkeypatch.setattr(reviews_module, "pick_direction", lambda: "target")

    await due_poll(context)

    review_service.mark_awaiting.assert_not_awaited()
