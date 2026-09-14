from __future__ import annotations

import random
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from vocab_bot.persistence import Card
from vocab_bot.services.reviews import ReviewService, build_due_card, pick_direction


def _card(card_id: int = 10) -> Card:
    now = datetime.now(tz=UTC)
    return Card(
        id=card_id,
        user_id=123,
        source_text="hello",
        target_text="privet",
        source_lang="EN",
        target_lang="RU",
        ease_factor=2.5,
        interval_days=1.0,
        repetition=2,
        next_review_at=now,
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

    repo.get.assert_awaited_once_with(1, 2)


def test_build_due_card_source_direction_prompts_with_target_side() -> None:
    due = build_due_card(_card(), "source")

    assert due.prompt_text == "privet"
    assert due.prompt_lang == "RU"
    assert due.answer_text == "hello"
    assert due.answer_lang == "EN"
    assert due.direction == "source"


def test_build_due_card_target_direction_prompts_with_source_side() -> None:
    due = build_due_card(_card(), "target")

    assert due.prompt_text == "hello"
    assert due.prompt_lang == "EN"
    assert due.answer_text == "privet"
    assert due.answer_lang == "RU"


def test_pick_direction_uses_given_rng() -> None:
    assert pick_direction(random.Random(0)) in {"source", "target"}
    assert pick_direction() in {"source", "target"}


@pytest.mark.asyncio
async def test_list_due_cards_for_user_keeps_repo_order_and_resolves_direction() -> None:
    repo = AsyncMock()
    repo.list_due_for_user.return_value = [_card(1), _card(2), _card(3)]
    service = ReviewService(repo, rng=random.Random(42))

    due = await service.list_due_cards_for_user(user_id=123, limit=10)

    assert [d.card.id for d in due] == [1, 2, 3]
    assert all(d.direction in {"source", "target"} for d in due)
    repo.list_due_for_user.assert_awaited_once_with(123, limit=10)


@pytest.mark.asyncio
async def test_list_due_cards_for_user_promotes_first_card_id() -> None:
    repo = AsyncMock()
    repo.list_due_for_user.return_value = [_card(1), _card(2), _card(3)]
    service = ReviewService(repo, rng=random.Random(1))

    due = await service.list_due_cards_for_user(user_id=123, first_card_id=3)

    assert [d.card.id for d in due] == [3, 1, 2]


@pytest.mark.asyncio
async def test_list_due_cards_for_user_ignores_unknown_first_card_id() -> None:
    repo = AsyncMock()
    repo.list_due_for_user.return_value = [_card(1), _card(2)]
    service = ReviewService(repo)

    due = await service.list_due_cards_for_user(user_id=123, first_card_id=99)

    assert [d.card.id for d in due] == [1, 2]


@pytest.mark.asyncio
async def test_count_due_for_user_passthrough() -> None:
    repo = AsyncMock()
    repo.count_due_for_user.return_value = 5
    service = ReviewService(repo)

    assert await service.count_due_for_user(user_id=123) == 5
    repo.count_due_for_user.assert_awaited_once_with(123)
