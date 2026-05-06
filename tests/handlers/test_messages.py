from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import messages as messages_module
from vocab_bot.handlers.messages import _grade_keyboard, on_text_message
from vocab_bot.persistence.types import Card, PendingTranslation
from vocab_bot.translate import TranslationError


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="EN",
        target_lang="RU",
        available_languages=frozenset({"EN", "RU"}),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
    )


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(),
                "review_service": AsyncMock(),
                "translation_service": AsyncMock(),
                "http_client": object(),
            }
        ),
        bot=AsyncMock(),
    )


def _update(text: str = "hello", message_id: int = 11) -> SimpleNamespace:
    message = SimpleNamespace(
        message_id=message_id,
        text=text,
        reply_text=AsyncMock(),
        reply_html=AsyncMock(),
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_message=message,
    )


@pytest.mark.asyncio
async def test_on_text_message_replies_access_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("hello")
    context = _ctx()
    monkeypatch.setattr(messages_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=False)))

    await on_text_message(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_text_message_handles_awaiting_card_and_delete_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update = _update("guess")
    context = _ctx()
    review_service = context.application.bot_data["review_service"]
    review_service.get_awaiting_card_for_user.return_value = Card(
        id=9,
        user_id=123,
        source_text="hello",
        target_text="privet",
        source_lang="EN",
        target_lang="RU",
        ease_factor=2.5,
        interval_days=1.0,
        repetition=1,
        next_review_at=datetime.now(tz=UTC),
        awaiting_grade=True,
    )
    context.application.bot_data["awaiting_review_messages"] = {(123, 9): 77}
    context.application.bot_data["awaiting_review_directions"] = {(123, 9): "target"}
    context.bot.delete_message.side_effect = RuntimeError("boom")
    monkeypatch.setattr(messages_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_text_message(update, context)

    context.bot.delete_message.assert_awaited_once_with(chat_id=123, message_id=77)
    update.effective_message.reply_html.assert_awaited_once()
    context.application.bot_data["translation_service"].translate_and_store_pending.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_text_message_translate_error_replied(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("hello")
    context = _ctx()
    context.application.bot_data["review_service"].get_awaiting_card_for_user.return_value = None
    context.application.bot_data["translation_service"].translate_and_store_pending.side_effect = TranslationError(
        "nope"
    )
    monkeypatch.setattr(messages_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_text_message(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_text_message_unexpected_error_replied(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("hello")
    context = _ctx()
    context.application.bot_data["review_service"].get_awaiting_card_for_user.return_value = None
    context.application.bot_data["translation_service"].translate_and_store_pending.side_effect = RuntimeError("fail")
    monkeypatch.setattr(messages_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_text_message(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_text_message_translation_success_builds_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("hello", message_id=99)
    context = _ctx()
    context.application.bot_data["review_service"].get_awaiting_card_for_user.return_value = None
    context.application.bot_data["translation_service"].translate_and_store_pending.return_value = PendingTranslation(
        id="p1",
        user_id=123,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet", "zdravstvuyte"),
    )
    monkeypatch.setattr(messages_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_text_message(update, context)

    assert update.effective_message.reply_html.await_count == 1
    _, kwargs = update.effective_message.reply_html.await_args
    keyboard = kwargs["reply_markup"]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "save:p1:0:99" in callbacks
    assert "dismiss:p1" in callbacks


def test_grade_keyboard_has_three_grades() -> None:
    keyboard = _grade_keyboard(10, "en")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["grade:10:0", "grade:10:3", "grade:10:5"]
