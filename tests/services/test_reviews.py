from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from vocab_bot.persistence import Card
from vocab_bot.services.reviews import ReviewService


def _card() -> Card:
    now = datetime.now(tz=UTC)
    return Card(
        id=10,
        user_id=123,
        source_text="hello",
        target_text="privet",
        source_lang="EN",
        target_lang="RU",
        ease_factor=2.5,
        interval_days=1.0,
        repetition=2,
        next_review_at=now,
        awaiting_grade=False,
    )


@pytest.mark.asyncio
async def test_apply_grade_returns_none_when_card_missing() -> None:
    repo = AsyncMock()
    repo.get.return_value = None
    service = ReviewService(repo)

    result = await service.apply_grade(card_id=1, user_id=2, quality=3)

    assert result is None
    repo.update_srs.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_grade_updates_repo_and_returns_result() -> None:
    repo = AsyncMock()
    repo.get.return_value = _card()
    service = ReviewService(repo)

    result = await service.apply_grade(card_id=10, user_id=123, quality=5)

    assert result is not None
    assert result.repetition >= 1
    repo.update_srs.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_service_passthrough_methods() -> None:
    repo = AsyncMock()
    service = ReviewService(repo)

    await service.get_card_for_user(card_id=1, user_id=2)
    await service.list_due_cards(limit=8)
    await service.mark_awaiting(card_id=1, user_id=2, awaiting=True)

    repo.get.assert_awaited_once_with(1, 2)
    repo.list_due.assert_awaited_once_with(limit=8)
    repo.mark_awaiting.assert_awaited_once_with(1, 2, True)
