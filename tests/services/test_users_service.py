from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.helpers import make_user
from vocab_bot.services.users import UserService


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
