from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.config import Settings
from vocab_bot.handlers import commands as commands_module
from vocab_bot.handlers.commands import _set_user_access, cmd_block_user


def _settings(admin_ids: frozenset[int] = frozenset()) -> Settings:
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
        admin_user_ids=admin_ids,
    )


def _context(args: list[str], admin_ids: frozenset[int] = frozenset()) -> SimpleNamespace:
    return SimpleNamespace(
        args=args,
        application=SimpleNamespace(
            bot_data={
                "settings": _settings(admin_ids),
                "user_service": AsyncMock(),
            }
        ),
    )


def _update() -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=500),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_set_user_access_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _context(["1"])
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=False))

    await _set_user_access(update, context, allowed=True)

    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_user_access_replies_usage_for_invalid_target(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _context(["bad"])
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=True))

    await _set_user_access(update, context, allowed=True)

    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_user_access_prevents_blocking_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _context(["42"], admin_ids=frozenset({42}))
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=True))

    await _set_user_access(update, context, allowed=False)

    update.effective_message.reply_text.assert_awaited_once()
    context.application.bot_data["user_service"].set_allowed.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_user_access_updates_user(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _context(["42"])
    monkeypatch.setattr(commands_module, "require_admin", AsyncMock(return_value=True))
    context.application.bot_data["user_service"].set_allowed.return_value = make_user(telegram_id=42, is_allowed=True)

    await _set_user_access(update, context, allowed=True)

    context.application.bot_data["user_service"].set_allowed.assert_awaited_once_with(42, True)
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cmd_block_user_delegates_to_shared_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update()
    context = _context(["42"])
    helper = AsyncMock()
    monkeypatch.setattr(commands_module, "_set_user_access", helper)

    await cmd_block_user(update, context)

    helper.assert_awaited_once_with(update, context, allowed=False)
