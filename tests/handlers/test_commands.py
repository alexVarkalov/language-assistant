from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import commands as commands_module
from vocab_bot.handlers.commands import (
    cmd_languages,
    cmd_locale,
    cmd_menu,
    cmd_quicklangs,
    cmd_start,
    cmd_timezone,
    cmd_users,
)


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
        admin_user_ids=frozenset({999}),
    )


def _ctx(args: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        args=list(args or []),
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(),
                "user_service": AsyncMock(),
            }
        ),
    )


def _update(with_user: bool = True, with_message: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=123) if with_user else None,
        effective_message=SimpleNamespace(
            reply_text=AsyncMock(),
            reply_html=AsyncMock(),
        )
        if with_message
        else None,
    )


@pytest.mark.asyncio
async def test_cmd_start_no_message_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update(with_message=False)
    context = _ctx()
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await cmd_start(update, context)


@pytest.mark.asyncio
async def test_cmd_start_access_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=False)))

    await cmd_start(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_start_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(
        commands_module,
        "record_user_seen",
        AsyncMock(return_value=make_user(is_allowed=True, timezone="UTC", preferred_locale="en")),
    )

    await cmd_start(update, context)

    update.effective_message.reply_html.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_users_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=False))

    await cmd_users(update, context)

    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_users_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=True))
    context.application.bot_data["user_service"].list_recent.return_value = []

    await cmd_users(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_users_formats_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx()
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=True))
    user1 = make_user(telegram_id=1, username="a", preferred_source_lang=None, preferred_target_lang=None)
    user2 = make_user(telegram_id=2, username=None, first_name="B", last_name="C", is_allowed=False)
    user2 = make_user(
        telegram_id=2,
        username=None,
        first_name="B",
        last_name="C",
        is_allowed=False,
        timezone="UTC",
        preferred_source_lang="PL",
        preferred_target_lang="EN",
        last_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    context.application.bot_data["user_service"].list_recent.return_value = [user1, user2]

    await cmd_users(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_timezone_missing_user_or_message_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _ctx()
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user()))

    await cmd_timezone(_update(with_user=False), context)
    await cmd_timezone(_update(with_message=False), context)


@pytest.mark.asyncio
async def test_cmd_timezone_current(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx([])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))

    await cmd_timezone(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_timezone_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["Bad/Zone"])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))
    context.application.bot_data["user_service"].set_timezone.side_effect = ValueError("bad")

    await cmd_timezone(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_timezone_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["UTC"])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))
    context.application.bot_data["user_service"].set_timezone.return_value = make_user(timezone="UTC")

    await cmd_timezone(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_languages_current_when_insufficient_args(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["EN"])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))

    await cmd_languages(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_languages_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["EN", "ZZ"])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))

    await cmd_languages(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_languages_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["pl", "ru"])
    monkeypatch.setattr(commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True)))

    await cmd_languages(update, context)

    context.application.bot_data["user_service"].set_languages.assert_awaited_once_with(123, "PL", "RU")
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_locale_current_when_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx([])
    monkeypatch.setattr(
        commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True, preferred_locale="en"))
    )

    await cmd_locale(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_locale_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["de"])
    monkeypatch.setattr(
        commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True, preferred_locale="en"))
    )

    await cmd_locale(update, context)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_locale_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx(["ru"])
    monkeypatch.setattr(
        commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True, preferred_locale="en"))
    )
    context.application.bot_data["user_service"].set_locale.return_value = make_user(
        is_allowed=True, preferred_locale="ru"
    )

    await cmd_locale(update, context)

    context.application.bot_data["user_service"].set_locale.assert_awaited_once_with(123, "ru")
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_menu_and_quicklangs(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _ctx([])
    monkeypatch.setattr(
        commands_module, "record_user_seen", AsyncMock(return_value=make_user(is_allowed=True, preferred_locale="en"))
    )

    await cmd_menu(update, context)
    await cmd_quicklangs(update, context)

    assert update.effective_message.reply_html.await_count == 1
    assert update.effective_message.reply_text.await_count == 1
