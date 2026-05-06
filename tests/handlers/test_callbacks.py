from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import callbacks as callbacks_module
from vocab_bot.handlers.callbacks import on_callback
from vocab_bot.persistence.types import Card, PendingTranslation


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="EN",
        target_lang="RU",
        available_languages=frozenset({"EN", "RU", "PL"}),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
    )


def _query(data: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(),
                "translation_service": AsyncMock(),
                "review_service": AsyncMock(),
                "user_service": AsyncMock(),
            }
        ),
        bot=AsyncMock(),
    )


def _update(data: str, user_id: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        callback_query=_query(data),
        effective_user=SimpleNamespace(id=user_id),
    )


@pytest.mark.asyncio
async def test_on_callback_save_pending_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("save:p1:0:55")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["translation_service"].save_pending_as_card.return_value = None

    await on_callback(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_save_success_deletes_source_message(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("save:p1:1:55")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["translation_service"].save_pending_as_card.return_value = PendingTranslation(
        id="p1",
        user_id=123,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet",),
    )

    await on_callback(update, context)

    context.bot.delete_message.assert_awaited_once_with(chat_id=123, message_id=55)
    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_dismiss(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("dismiss:pid")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_callback(update, context)

    context.application.bot_data["translation_service"].dismiss_pending.assert_awaited_once_with(
        pending_id="pid", user_id=123
    )
    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_reveal_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("reveal:10:source")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["review_service"].get_card_for_user.return_value = None

    await on_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_reveal_success(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("reveal:10:target")
    context = _ctx()
    context.application.bot_data["awaiting_review_messages"] = {(123, 10): 1}
    context.application.bot_data["awaiting_review_directions"] = {(123, 10): "target"}
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["review_service"].get_card_for_user.return_value = Card(
        id=10,
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

    await on_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_grade_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("grade:11:3")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["review_service"].apply_grade.return_value = None

    await on_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_grade_success(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("grade:11:5")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))
    context.application.bot_data["review_service"].apply_grade.return_value = SimpleNamespace(
        next_review_at=datetime.now(tz=UTC),
        repetition=3,
        interval_days=4.5,
        ease_factor=2.7,
    )

    await on_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ["menu:open", "menu:locale", "menu:pair"])
async def test_on_callback_menu_branches(monkeypatch: pytest.MonkeyPatch, data: str) -> None:
    update = _update(data)
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_set_locale_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("menu:set_locale:de")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_callback(update, context)

    assert update.callback_query.answer.await_count == 2


@pytest.mark.asyncio
async def test_on_callback_set_locale_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("menu:set_locale:ru")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user(preferred_locale="en")))
    context.application.bot_data["user_service"].set_locale.return_value = make_user(preferred_locale="ru")

    await on_callback(update, context)

    context.application.bot_data["user_service"].set_locale.assert_awaited_once_with(123, "ru")
    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_callback_set_pair_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("menu:set_pair:EN:ZZ")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_callback(update, context)

    assert update.callback_query.answer.await_count == 2


@pytest.mark.asyncio
async def test_on_callback_set_pair_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("menu:set_pair:PL:RU")
    context = _ctx()
    monkeypatch.setattr(callbacks_module, "record_user_seen", AsyncMock(return_value=make_user(preferred_locale="en")))
    context.application.bot_data["user_service"].set_languages.return_value = make_user(preferred_locale="ru")

    await on_callback(update, context)

    context.application.bot_data["user_service"].set_languages.assert_awaited_once_with(123, "PL", "RU")
    update.callback_query.edit_message_text.assert_awaited_once()
