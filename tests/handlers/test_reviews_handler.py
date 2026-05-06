from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.handlers import reviews as reviews_module
from vocab_bot.handlers.reviews import due_poll
from vocab_bot.persistence.types import Card


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


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "review_service": AsyncMock(),
                "user_service": AsyncMock(),
            }
        ),
        bot=AsyncMock(),
    )


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
    monkeypatch.setattr(reviews_module.random, "choice", lambda _: "source")

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
    monkeypatch.setattr(reviews_module.random, "choice", lambda _: "target")

    await due_poll(context)

    review_service.mark_awaiting.assert_not_awaited()
