from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from tests.helpers import make_user
from vocab_bot.services.notifications import (
    DueNotificationService,
    DueSummary,
    latest_slot_passed,
    reminder_hours,
    should_notify,
)

WARSAW = ZoneInfo("Europe/Warsaw")


def _at(hour: int, minute: int = 0, *, tz: ZoneInfo = WARSAW) -> datetime:
    return datetime(2026, 9, 14, hour, minute, tzinfo=tz)


def test_reminder_hours_per_option_and_fallback() -> None:
    assert reminder_hours(1) == (9,)
    assert reminder_hours(2) == (9, 19)
    assert reminder_hours(3) == (9, 14, 19)
    assert reminder_hours(0) == reminder_hours(1)
    assert reminder_hours(7) == reminder_hours(1)


def test_latest_slot_passed_uses_user_timezone() -> None:
    user = make_user(timezone="Europe/Warsaw", reminders_per_day=2)
    assert latest_slot_passed(user, now=_at(8, 59)) is None
    assert latest_slot_passed(user, now=_at(9, 0)) == _at(9)
    assert latest_slot_passed(user, now=_at(18, 59)) == _at(9)
    assert latest_slot_passed(user, now=_at(23, 30)) == _at(19)
    # 07:30 UTC is 09:30 in Warsaw: the morning slot has passed there, not in UTC.
    assert latest_slot_passed(user, now=datetime(2026, 9, 14, 7, 30, tzinfo=UTC)) == _at(9)
    assert latest_slot_passed(make_user(timezone=None, reminders_per_day=2), now=_at(7, 30, tz=UTC)) is None


def test_latest_slot_passed_falls_back_to_utc_for_unknown_timezone() -> None:
    user = make_user(timezone="Mars/Colony", reminders_per_day=1)
    assert latest_slot_passed(user, now=_at(9, 5, tz=UTC)) == _at(9, tz=UTC)


def test_should_notify_before_first_slot_of_the_day_is_false() -> None:
    assert not should_notify(make_user(due_notified_at=None, reminders_per_day=3), now=_at(8, 59))


def test_should_notify_when_never_notified_and_a_slot_passed() -> None:
    user = make_user(timezone="Europe/Warsaw", due_notified_at=None, reminders_per_day=1)
    assert should_notify(user, now=_at(9, 0))


def test_should_notify_once_per_slot() -> None:
    user = make_user(timezone="Europe/Warsaw", reminders_per_day=2, due_notified_at=_at(9, 1))
    assert not should_notify(user, now=_at(9, 2))
    assert not should_notify(user, now=_at(18, 59))
    assert should_notify(user, now=_at(19, 0))


def test_should_notify_is_not_repeated_when_queue_refills_between_slots() -> None:
    # Reminded at 09:01, reviewed everything, a card came due again at 10:00: wait for the next slot.
    user = make_user(timezone="Europe/Warsaw", reminders_per_day=1, due_notified_at=_at(9, 1))
    assert not should_notify(user, now=_at(10, 0))
    assert should_notify(user, now=_at(9, 0) + timedelta(days=1))


def test_should_notify_once_a_day_ignores_yesterdays_reminder() -> None:
    user = make_user(timezone="UTC", reminders_per_day=1, due_notified_at=_at(9, 0, tz=UTC) - timedelta(days=1))
    assert should_notify(user, now=_at(9, 0, tz=UTC))


def _service(
    card_repo: AsyncMock, user_repo: AsyncMock, admins: frozenset[int] = frozenset()
) -> DueNotificationService:
    return DueNotificationService(card_repo, user_repo, admin_user_ids=admins)


NOON = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_collect_returns_only_eligible_users() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {10: 3, 20: 1, 30: 2, 40: 4, 50: 0}
    user_repo.get.side_effect = [
        make_user(telegram_id=10, due_notified_at=None),
        make_user(telegram_id=20, due_notified_at=NOON - timedelta(minutes=5)),
        make_user(telegram_id=30, is_allowed=False),
        None,
    ]

    summaries = await _service(card_repo, user_repo).collect(now=NOON)

    assert summaries == [DueSummary(user=summaries[0].user, due_count=3)]
    assert summaries[0].user.telegram_id == 10
    assert user_repo.get.await_count == 4


@pytest.mark.asyncio
async def test_collect_lets_admins_bypass_allow_list() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {99: 1}
    user_repo.get.return_value = make_user(telegram_id=99, is_allowed=False)

    summaries = await _service(card_repo, user_repo, admins=frozenset({99})).collect(now=NOON)

    assert [s.user.telegram_id for s in summaries] == [99]


@pytest.mark.asyncio
async def test_collect_with_no_due_cards_touches_nobody() -> None:
    card_repo = AsyncMock()
    user_repo = AsyncMock()
    card_repo.count_due_by_user.return_value = {}

    assert await _service(card_repo, user_repo).collect(now=NOON) == []
    user_repo.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_notified_stamps_user() -> None:
    user_repo = AsyncMock()

    await _service(AsyncMock(), user_repo).mark_notified(10, now=NOON)

    user_repo.set_due_notified_at.assert_awaited_once_with(10, NOON)
