from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import wordbank as wordbank_module
from vocab_bot.handlers.wordbank import (
    PREVIEW_WORD_LIMIT,
    cmd_wordbank,
    on_wordbank_callback,
    sections_keyboard,
    topic_preview_text,
    topics_keyboard,
)
from vocab_bot.services.wordbank import WordbankAddResult
from vocab_bot.wordbank import Section, Topic, WordEntry


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="RU",
        target_lang="PL",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
        wordbank_path="data/ru_pl_dictionary.json",
    )


def _sections() -> tuple[Section, ...]:
    return (
        Section(
            title="основные понятия | часть 1",
            topics=(
                Topic(
                    number=1,
                    title="Местоимения",
                    words=(WordEntry(ru="я", pl="ja", ipa="[ja]"), WordEntry(ru="ты", pl="ty", ipa="[tɨ]")),
                ),
            ),
        ),
        Section(title="питание", topics=(Topic(number=3, title="Продукты", words=()),)),
    )


def _wordbank_service() -> Mock:
    service = Mock()
    service.list_sections.return_value = _sections()
    service.get_topic.side_effect = lambda number: next(
        ((section, topic) for section in _sections() for topic in section.topics if topic.number == number), None
    )
    service.add_topic_words = AsyncMock()
    return service


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(),
                "wordbank_service": _wordbank_service(),
            }
        ),
    )


def _update() -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )


def _query(data: str) -> SimpleNamespace:
    return SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())


def _callback_update(data: str) -> SimpleNamespace:
    return SimpleNamespace(callback_query=_query(data), effective_user=SimpleNamespace(id=123))


@pytest.mark.asyncio
async def test_cmd_wordbank_access_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=False)))

    await cmd_wordbank(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    args, kwargs = update.effective_message.reply_text.call_args
    assert "reply_markup" not in kwargs


@pytest.mark.asyncio
async def test_cmd_wordbank_shows_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))

    await cmd_wordbank(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    _, kwargs = update.effective_message.reply_text.call_args
    keyboard = kwargs["reply_markup"]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["wb:section:0", "wb:section:1"]


def test_sections_keyboard_one_button_per_section() -> None:
    keyboard = sections_keyboard(_sections())
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert labels == ["основные понятия | часть 1", "питание"]


def test_topics_keyboard_has_back_button() -> None:
    section = _sections()[0]
    keyboard = topics_keyboard("en", section)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == ["wb:topic:1", "wb:sections"]


def test_topic_preview_text_truncates_long_topics() -> None:
    words = tuple(WordEntry(ru=f"ru{i}", pl=f"pl{i}", ipa="[x]") for i in range(PREVIEW_WORD_LIMIT + 5))
    topic = Topic(number=1, title="Big topic", words=words)

    text = topic_preview_text("en", topic)

    assert "ru0 — pl0" in text
    assert f"ru{PREVIEW_WORD_LIMIT}" not in text
    assert "…and 5 more" in text


@pytest.mark.asyncio
async def test_on_wordbank_callback_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _callback_update("wb:sections")
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_wordbank_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_wordbank_callback_section(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _callback_update("wb:section:1")
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_wordbank_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()
    _, kwargs = update.callback_query.edit_message_text.call_args
    callbacks = [button.callback_data for row in kwargs["reply_markup"].inline_keyboard for button in row]
    assert callbacks == ["wb:topic:3", "wb:sections"]


@pytest.mark.asyncio
async def test_on_wordbank_callback_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _callback_update("wb:topic:1")
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_wordbank_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()
    _, kwargs = update.callback_query.edit_message_text.call_args
    callbacks = [button.callback_data for row in kwargs["reply_markup"].inline_keyboard for button in row]
    assert callbacks == ["wb:add:1", "wb:section:0"]


@pytest.mark.asyncio
async def test_on_wordbank_callback_topic_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _callback_update("wb:topic:999")
    context = _ctx()
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_wordbank_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()
    args, _ = update.callback_query.edit_message_text.call_args
    assert "no longer exists" in args[0] or "не существует" in args[0]


@pytest.mark.asyncio
async def test_on_wordbank_callback_add(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _callback_update("wb:add:1")
    context = _ctx()
    context.application.bot_data["wordbank_service"].add_topic_words.return_value = WordbankAddResult(
        topic_title="Местоимения", added=2, skipped=0
    )
    monkeypatch.setattr(wordbank_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await on_wordbank_callback(update, context)

    context.application.bot_data["wordbank_service"].add_topic_words.assert_awaited_once_with(
        user_id=123, topic_number=1
    )
    update.callback_query.edit_message_text.assert_awaited_once()
