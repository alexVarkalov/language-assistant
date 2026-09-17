from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.services.users import UserService, user_has_access, user_zone


def test_user_has_access_allowed_user() -> None:
    assert user_has_access(make_user(is_allowed=True), frozenset()) is True


def test_user_has_access_blocked_user() -> None:
    assert user_has_access(make_user(is_allowed=False), frozenset()) is False


def test_user_has_access_admin_bypasses_block() -> None:
    assert user_has_access(make_user(telegram_id=7, is_allowed=False), frozenset({7})) is True


@pytest.mark.asyncio
async def test_set_timezone_validates_and_calls_repo() -> None:
    repo = AsyncMock()
    repo.set_timezone.return_value = make_user(timezone="Europe/Warsaw")
    service = UserService(repo)

    result = await service.set_timezone(1, "Europe/Warsaw")

    assert result.timezone == "Europe/Warsaw"
    repo.set_timezone.assert_awaited_once_with(1, "Europe/Warsaw")


@pytest.mark.asyncio
async def test_set_timezone_rejects_invalid_timezone() -> None:
    repo = AsyncMock()
    service = UserService(repo)

    with pytest.raises(ValueError, match="Unknown timezone"):
        await service.set_timezone(1, "Mars/Colony")


@pytest.mark.asyncio
async def test_set_locale_normalizes_before_repo_call() -> None:
    repo = AsyncMock()
    repo.set_locale.return_value = make_user(preferred_locale="ru")
    service = UserService(repo)

    await service.set_locale(1, "RU")

    repo.set_locale.assert_awaited_once_with(1, "ru")


@pytest.mark.asyncio
@pytest.mark.parametrize("option", [1, 2, 3])
async def test_set_reminders_per_day_accepts_options(option: int) -> None:
    repo = AsyncMock()
    repo.set_reminders_per_day.return_value = make_user(reminders_per_day=option)
    service = UserService(repo)

    result = await service.set_reminders_per_day(1, option)

    assert result.reminders_per_day == option
    repo.set_reminders_per_day.assert_awaited_once_with(1, option)


@pytest.mark.asyncio
@pytest.mark.parametrize("option", [0, 4, -1])
async def test_set_reminders_per_day_rejects_other_values(option: int) -> None:
    repo = AsyncMock()
    service = UserService(repo)

    with pytest.raises(ValueError, match="reminders_per_day"):
        await service.set_reminders_per_day(1, option)
    repo.set_reminders_per_day.assert_not_awaited()


def test_user_zone_falls_back_to_utc() -> None:
    assert user_zone(make_user(timezone="Europe/Warsaw")).key == "Europe/Warsaw"
    assert user_zone(make_user(timezone=None)).key == "UTC"
    assert user_zone(make_user(timezone="Mars/Colony")).key == "UTC"
