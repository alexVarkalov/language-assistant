from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from vocab_bot.repositories.cards import CardRepository


@pytest.mark.asyncio
async def test_card_repository_forwards_upsert_to_db() -> None:
    db = AsyncMock()
    db.upsert_card.return_value = 99
    repo = CardRepository(db)
    when = datetime(2026, 1, 1, tzinfo=UTC)

    card_id = await repo.upsert(
        user_id=1,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        ease_factor=2.5,
        interval_days=0.0,
        repetition=0,
        next_review_at=when,
    )

    assert card_id == 99
    db.upsert_card.assert_awaited_once()


@pytest.mark.asyncio
async def test_card_repository_forwards_insert_if_missing_to_db() -> None:
    db = AsyncMock()
    db.insert_card_if_missing.return_value = True
    repo = CardRepository(db)
    when = datetime(2026, 1, 1, tzinfo=UTC)

    inserted = await repo.insert_if_missing(
        user_id=1,
        source_lang="RU",
        target_lang="PL",
        source_text="кот",
        target_text="kot",
        ease_factor=2.5,
        interval_days=0.0,
        repetition=0,
        next_review_at=when,
    )

    assert inserted is True
    db.insert_card_if_missing.assert_awaited_once()


@pytest.mark.asyncio
async def test_card_repository_get_and_list_due() -> None:
    db = AsyncMock()
    db.get_card.return_value = object()
    db.list_due_cards.return_value = [object()]
    db.get_awaiting_card.return_value = object()
    repo = CardRepository(db)

    await repo.get(10, 20)
    await repo.get_awaiting(20)
    await repo.list_due(limit=7)

    db.get_card.assert_awaited_once_with(10, 20)
    db.get_awaiting_card.assert_awaited_once_with(20)
    db.list_due_cards.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_card_repository_per_user_due_queue() -> None:
    db = AsyncMock()
    db.list_due_cards_for_user.return_value = [object()]
    db.count_due_cards_for_user.return_value = 4
    repo = CardRepository(db)

    cards = await repo.list_due_for_user(20, limit=7)
    count = await repo.count_due_for_user(20)

    assert len(cards) == 1
    assert count == 4
    db.list_due_cards_for_user.assert_awaited_once_with(20, 7)
    db.count_due_cards_for_user.assert_awaited_once_with(20)


@pytest.mark.asyncio
async def test_card_repository_count_due_by_user_forwards() -> None:
    db = AsyncMock()
    db.count_due_cards_by_user.return_value = {1: 2}

    assert await CardRepository(db).count_due_by_user() == {1: 2}
