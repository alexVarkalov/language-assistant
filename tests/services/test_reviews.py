from __future__ import annotations

import random
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from vocab_bot.persistence import Card
from vocab_bot.services.reviews import (
    ReviewService,
    build_due_card,
    direction_for_card,
    pick_direction,
    review_stage,
)


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


def _pl_ru_card(*, repetition: int, source_lang: str = "PL", target_lang: str = "RU") -> Card:
    """A card whose source side is Polish and target side Russian, unless swapped."""
    now = datetime.now(tz=UTC)
    texts = {"PL": "dom", "RU": "\u0434\u043e\u043c", "EN": "house"}
    return Card(
        id=1,
        user_id=123,
        source_text=texts[source_lang],
        target_text=texts[target_lang],
        source_lang=source_lang,
        target_lang=target_lang,
        ease_factor=2.5,
        interval_days=1.0,
        repetition=repetition,
        next_review_at=now,
    )


@pytest.mark.parametrize(
    ("repetition", "expected"),
    [(0, "recognition"), (2, "recognition"), (3, "mixed"), (5, "mixed"), (6, "production"), (30, "production")],
)
def test_review_stage_follows_repetition(repetition: int, expected: str) -> None:
    assert review_stage(repetition) == expected


@pytest.mark.parametrize("source_lang", ["PL", "RU"])
def test_new_card_prompts_with_the_foreign_word(source_lang: str) -> None:
    target_lang = "RU" if source_lang == "PL" else "PL"
    card = _pl_ru_card(repetition=0, source_lang=source_lang, target_lang=target_lang)

    due = build_due_card(card, direction_for_card(card, "RU"))

    assert due.prompt_lang == "PL"
    assert due.answer_lang == "RU"


@pytest.mark.parametrize("source_lang", ["PL", "RU"])
def test_well_known_card_prompts_with_the_native_word(source_lang: str) -> None:
    target_lang = "RU" if source_lang == "PL" else "PL"
    card = _pl_ru_card(repetition=9, source_lang=source_lang, target_lang=target_lang)

    due = build_due_card(card, direction_for_card(card, "RU"))

    assert due.prompt_lang == "RU"
    assert due.answer_lang == "PL"


def test_mid_stage_card_uses_both_directions() -> None:
    card = _pl_ru_card(repetition=4)
    rng = random.Random(7)

    seen = {direction_for_card(card, "RU", rng) for _ in range(40)}

    assert seen == {"source", "target"}


def test_direction_is_random_without_a_native_language() -> None:
    card = _pl_ru_card(repetition=0)
    rng = random.Random(7)

    seen = {direction_for_card(card, None, rng) for _ in range(40)}

    assert seen == {"source", "target"}


def test_direction_is_random_when_no_card_side_is_native() -> None:
    card = _pl_ru_card(repetition=0, source_lang="PL", target_lang="EN")
    rng = random.Random(7)

    seen = {direction_for_card(card, "RU", rng) for _ in range(40)}

    assert seen == {"source", "target"}


@pytest.mark.asyncio
async def test_list_due_cards_uses_the_stage_direction() -> None:
    repo = AsyncMock()
    repo.list_due_for_user.return_value = [_pl_ru_card(repetition=0), _pl_ru_card(repetition=9)]
    service = ReviewService(repo, native_lang="RU")

    new_card, known_card = await service.list_due_cards_for_user(user_id=123)

    assert (new_card.prompt_lang, new_card.answer_lang) == ("PL", "RU")
    assert (known_card.prompt_lang, known_card.answer_lang) == ("RU", "PL")
