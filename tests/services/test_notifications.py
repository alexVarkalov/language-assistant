from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.services.notifications import DueNotificationService, DueSummary, should_notify

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
COOLDOWN = timedelta(hours=4)


def test_should_notify_when_never_notified() -> None:
    assert should_notify(make_user(due_notified_at=None), now=NOW, cooldown=COOLDOWN)


def test_should_not_notify_inside_cooldown() -> None:
    user = make_user(due_notified_at=NOW - timedelta(hours=1))
    assert not should_notify(user, now=NOW, cooldown=COOLDOWN)


def test_should_notify_once_cooldown_elapsed() -> None:
    user = make_user(due_notified_at=NOW - COOLDOWN)
    assert should_notify(user, now=NOW, cooldown=COOLDOWN)


def _service(
    card_repo: AsyncMock, user_repo: AsyncMock, admins: frozenset[int] = frozenset()
) -> DueNotificationService:
    return DueNotificationService(card_repo, user_repo, admin_user_ids=admins, cooldown_minutes=240)


@pytest.mark.asyncio
async def test_collect_resets_users_without_due_cards_and_returns_eligible() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {10: 3, 20: 1, 30: 2, 40: 4}
    user_repo.get.side_effect = [
        make_user(telegram_id=10, due_notified_at=None),
        make_user(telegram_id=20, due_notified_at=NOW - timedelta(minutes=5)),
        make_user(telegram_id=30, is_allowed=False),
        None,
    ]

    summaries = await _service(card_repo, user_repo).collect(now=NOW)

    user_repo.clear_due_notified_except.assert_awaited_once_with([10, 20, 30, 40])
    assert summaries == [DueSummary(user=summaries[0].user, due_count=3)]
    assert summaries[0].user.telegram_id == 10


@pytest.mark.asyncio
async def test_collect_lets_admins_bypass_allow_list() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {99: 1}
    user_repo.get.return_value = make_user(telegram_id=99, is_allowed=False)

    summaries = await _service(card_repo, user_repo, admins=frozenset({99})).collect(now=NOW)

    assert [s.user.telegram_id for s in summaries] == [99]


@pytest.mark.asyncio
async def test_collect_with_no_due_cards_clears_everyone() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {}

    assert await _service(card_repo, user_repo).collect(now=NOW) == []
    user_repo.clear_due_notified_except.assert_awaited_once_with([])
    user_repo.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_notified_stamps_user() -> None:
    user_repo = AsyncMock()

    await _service(AsyncMock(), user_repo).mark_notified(10, now=NOW)

    user_repo.set_due_notified_at.assert_awaited_once_with(10, NOW)
