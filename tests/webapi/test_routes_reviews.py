from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import make_user
from tests.webapi.conftest import auth_header
from vocab_bot.persistence import Card
from vocab_bot.services import GradeResult, build_due_card

WHEN = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)


def _card(card_id: int = 42) -> Card:
    return Card(
        id=card_id,
        user_id=123,
        source_text="dom",
        target_text="дом",
        source_lang="PL",
        target_lang="RU",
        ease_factor=2.5,
        interval_days=6.0,
        repetition=2,
        next_review_at=WHEN,
    )


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def authed_app(app: FastAPI) -> FastAPI:
    app.state.user_service.record_seen.return_value = make_user(telegram_id=123)
    return app


@pytest.mark.asyncio
async def test_queue_returns_resolved_cards(authed_app: FastAPI) -> None:
    review_service = authed_app.state.review_service
    review_service.list_due_cards_for_user.return_value = [build_due_card(_card(), "target")]
    review_service.count_due_for_user.return_value = 12

    async with _client(authed_app) as client:
        response = await client.get("/api/reviews/queue", headers=auth_header())

    assert response.status_code == 200
    assert response.json() == {
        "cards": [
            {
                "id": 42,
                "direction": "target",
                "prompt_text": "dom",
                "prompt_lang": "PL",
                "answer_text": "дом",
                "answer_lang": "RU",
                "repetition": 2,
                "interval_days": 6.0,
                "next_review_at": "2026-09-13T08:00:00Z",
            }
        ],
        "total_due": 12,
    }
    review_service.list_due_cards_for_user.assert_awaited_once_with(user_id=123, limit=50, first_card_id=None)


@pytest.mark.asyncio
async def test_queue_passes_limit_and_first(authed_app: FastAPI) -> None:
    review_service = authed_app.state.review_service
    review_service.list_due_cards_for_user.return_value = []
    review_service.count_due_for_user.return_value = 0

    async with _client(authed_app) as client:
        response = await client.get("/api/reviews/queue?limit=5&first=42", headers=auth_header())

    assert response.status_code == 200
    review_service.list_due_cards_for_user.assert_awaited_once_with(user_id=123, limit=5, first_card_id=42)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=abc", "first=0"])
async def test_queue_rejects_bad_query(authed_app: FastAPI, query: str) -> None:
    async with _client(authed_app) as client:
        response = await client.get(f"/api/reviews/queue?{query}", headers=auth_header())

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
    authed_app.state.review_service.list_due_cards_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_grade_happy_path(authed_app: FastAPI) -> None:
    review_service = authed_app.state.review_service
    review_service.apply_grade.return_value = GradeResult(
        next_review_at=WHEN, ease_factor=2.6, interval_days=15.0, repetition=3
    )

    async with _client(authed_app) as client:
        response = await client.post("/api/reviews/42/grade", json={"quality": 3}, headers=auth_header())

    assert response.status_code == 200
    assert response.json() == {
        "card_id": 42,
        "next_review_at": "2026-09-13T08:00:00Z",
        "interval_days": 15.0,
        "ease_factor": 2.6,
        "repetition": 3,
    }
    review_service.apply_grade.assert_awaited_once_with(card_id=42, user_id=123, quality=3)


@pytest.mark.asyncio
async def test_grade_unknown_card_is_404(authed_app: FastAPI) -> None:
    authed_app.state.review_service.apply_grade.return_value = None

    async with _client(authed_app) as client:
        response = await client.post("/api/reviews/999/grade", json={"quality": 5}, headers=auth_header())

    assert response.status_code == 404
    assert response.json()["error"] == "card_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize("quality", [1, 2, 4, 7, -1, "good"])
async def test_grade_rejects_unsupported_quality(authed_app: FastAPI, quality: object) -> None:
    async with _client(authed_app) as client:
        response = await client.post("/api/reviews/42/grade", json={"quality": quality}, headers=auth_header())

    assert response.status_code == 422
    authed_app.state.review_service.apply_grade.assert_not_awaited()


@pytest.mark.asyncio
async def test_grade_requires_auth(app: FastAPI) -> None:
    async with _client(app) as client:
        response = await client.post("/api/reviews/42/grade", json={"quality": 3})

    assert response.status_code == 401
